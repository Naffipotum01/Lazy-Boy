import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    import cv2
    _HAVE_CV2 = True
except Exception:
    _HAVE_CV2 = False


class ClickPredictor:
    def __init__(self):
        self._last_frame = None
        self._last_predictions = []
        self._ocr_available = self._check_ocr()
        self._font = None

    def _get_font(self, size=14):
        if self._font is None:
            try:
                self._font = ImageFont.truetype("arial.ttf", size)
            except Exception:
                try:
                    self._font = ImageFont.truetype("DejaVuSans.ttf", size)
                except Exception:
                    self._font = ImageFont.load_default()
        return self._font

    def _check_ocr(self):
        try:
            import easyocr
            self._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            return True
        except Exception:
            self._reader = None
            return False

    def _find_button_regions(self, gray):
        if not _HAVE_CV2:
            return []
        regions = []
        h, w = gray.shape

        edges = cv2.Canny(gray, 30, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = bw * bh
            screen_area = h * w
            if area < screen_area * 0.001 or area > screen_area * 0.3:
                continue
            if bw < 30 or bh < 20:
                continue
            aspect = bw / max(bh, 1)
            if aspect > 8 or aspect < 0.3:
                continue

            rect_area = bw * bh
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = rect_area / max(hull_area, 1) if hull_area > 0 else 0

            score = 0.5
            center_x = x + bw / 2
            center_y = y + bh / 2
            dist_from_center = np.sqrt((center_x / w - 0.5) ** 2 + (center_y / h - 0.5) ** 2)
            score += (1 - dist_from_center * 1.5) * 0.3

            if 1.5 < aspect < 4:
                score += 0.15
            if solidity > 0.7:
                score += 0.1

            roi = gray[y : y + bh, x : x + bw]
            text = self._read_text(roi)
            if text:
                score += 0.2
                if any(kw in text.lower() for kw in ["search", "submit", "send", "next",
                                                       "ok", "yes", "no", "save",
                                                       "open", "play", "start"]):
                    score += 0.15

            regions.append({
                "x": int(x), "y": int(y),
                "w": int(bw), "h": int(bh),
                "cx": int(center_x), "cy": int(center_y),
                "score": float(score),
                "text": text or "",
            })

        return regions

    def _find_text_regions(self, gray):
        if not _HAVE_CV2:
            return []
        regions = []
        h, w = gray.shape

        mser = cv2.MSER_create()
        try:
            _, boxes = mser.detectRegions(gray)
            for box in boxes:
                x, y, bw, bh = cv2.boundingRect(box)
                area = bw * bh
                if area < 200 or area > h * w * 0.1:
                    continue
                regions.append({
                    "x": int(x), "y": int(y),
                    "w": int(bw), "h": int(bh),
                    "cx": int(x + bw / 2), "cy": int(y + bh / 2),
                    "score": 0.4,
                    "text": "",
                })
        except Exception:
            pass

        return regions

    def _read_text(self, roi):
        if not self._ocr_available or not self._reader:
            return ""
        try:
            pil_img = Image.fromarray(roi)
            results = self._reader.readtext(np.array(pil_img),
                                              paragraph=True,
                                              width_ths=0.7)
            texts = [r[1] for r in results if r[2] > 0.3]
            return " ".join(texts)[:60] if texts else ""
        except Exception:
            return ""

    def predict(self, pil_image):
        gray = np.array(pil_image.convert("L"))
        h, w = gray.shape

        buttons = self._find_button_regions(gray)
        text_regions = self._find_text_regions(gray)

        seen = set()
        merged = []
        for r in buttons + text_regions:
            key = (r["x"] // 10, r["y"] // 10)
            if key not in seen:
                seen.add(key)
                merged.append(r)

        merged.sort(key=lambda r: -r["score"])
        top3 = merged[:3]

        for r in top3:
            text = self._read_text(gray[r["y"]:r["y"]+r["h"], r["x"]:r["x"]+r["w"]])
            if text:
                r["text"] = text
                r["score"] += 0.2

        self._last_predictions = top3
        return top3

    def render_overlay(self, pil_image, predictions):
        img = pil_image.copy()
        draw = ImageDraw.Draw(img, "RGBA")

        colors = [(0, 200, 50, 200), (50, 150, 255, 200), (255, 100, 50, 200)]
        bg_colors = [(0, 200, 50, 60), (50, 150, 255, 60), (255, 100, 50, 60)]

        for i, pred in enumerate(predictions):
            num = i + 1
            cx, cy = pred["cx"], pred["cy"]
            x, y, bw, bh = pred["x"], pred["y"], pred["w"], pred["h"]

            for j in range(3, 0, -1):
                alpha = 0.08 * (4 - j)
                bb = bg_colors[i]
                cb = (bb[0], bb[1], bb[2], int(alpha * 255))
                offset = 3 - j
                draw.rectangle(
                    [x - offset, y - offset, x + bw + offset, y + bh + offset],
                    outline=cb, width=1,
                )

            draw.rectangle([x, y, x + bw, y + bh], outline=colors[i], width=2)

            arrow_tip = (cx, y - 15)
            arrow_base = (cx, y - 5)
            draw.line([arrow_base, arrow_tip], fill=colors[i], width=2)

            dot_r = 12
            dot_cx, dot_cy = cx, y - 28
            draw.ellipse(
                [dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r],
                fill=(20, 20, 20, 220), outline=colors[i], width=2,
            )
            font = self._get_font(14)
            text_bbox = draw.textbbox((0, 0), str(num), font=font)
            tw = text_bbox[2] - text_bbox[0]
            th = text_bbox[3] - text_bbox[1]
            draw.text(
                (dot_cx - tw / 2, dot_cy - th / 2 - 1),
                str(num), fill=(255, 255, 255, 255), font=font,
            )

            if pred.get("text"):
                font_sm = self._get_font(11)
                draw.text(
                    (cx - 40, y - 45),
                    pred["text"][:30], fill=(255, 255, 255, 200),
                    font=font_sm,
                )

        return img

    def set_frame(self, pil_image):
        self._last_frame = pil_image
