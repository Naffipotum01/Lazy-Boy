import cv2
import numpy as np
from PIL import Image


class ClickPredictor:
    def __init__(self):
        self._last_frame = None
        self._last_predictions = []
        self._ocr_available = self._check_ocr()

    def _check_ocr(self):
        try:
            import easyocr
            self._reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            return True
        except Exception:
            self._reader = None
            return False

    def _find_button_regions(self, gray):
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
        import cv2
        import numpy as np
        img = np.array(pil_image)
        overlay = img.copy()

        for i, pred in enumerate(predictions):
            num = i + 1
            cx, cy = pred["cx"], pred["cy"]
            x, y, w, h = pred["x"], pred["y"], pred["w"], pred["h"]

            color = [(0, 200, 50), (50, 150, 255), (255, 100, 50)][i]
            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)

            arrow_tip = (cx, y - 15)
            arrow_base = (cx, y - 5)
            cv2.arrowedLine(overlay, arrow_base, arrow_tip, color, 2, tipLength=0.3)

            dot_center = (cx, y - 25)
            cv2.circle(overlay, dot_center, 12, (20, 20, 20), -1)
            cv2.circle(overlay, dot_center, 12, color, 2)
            cv2.putText(
                overlay, str(num),
                (dot_center[0] - 6, dot_center[1] + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2,
            )

            if pred.get("text"):
                text_y = y - 40
                cv2.putText(
                    overlay, pred["text"][:30],
                    (cx - 40, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1,
                )

        alpha = 0.85
        result = cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)
        return Image.fromarray(result)

    def set_frame(self, pil_image):
        self._last_frame = pil_image
