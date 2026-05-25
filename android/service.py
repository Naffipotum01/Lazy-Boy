import time
import os

try:
    from jnius import autoclass
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Context = autoclass("android.content.Context")
    NotificationManager = autoclass("android.app.NotificationManager")
    NotificationChannel = autoclass("android.app.NotificationChannel")
    NotificationCompat = autoclass("androidx.core.app.NotificationCompat")
    Build = autoclass("android.os.Build")
    R = autoclass("android.R")

    activity = PythonActivity.mActivity
    notificationManager = activity.getSystemService(Context.NOTIFICATION_SERVICE)

    channel_id = "lazyboy_foreground"
    if Build.VERSION.SDK_INT >= 26:
        channel = NotificationChannel(channel_id, "Lazy Boy Service", NotificationManager.IMPORTANCE_LOW)
        notificationManager.createNotificationChannel(channel)

    builder = NotificationCompat.Builder(activity, channel_id)
    builder.setContentTitle("Lazy Boy")
    builder.setContentText("Remote control service running")
    builder.setSmallIcon(android.R.drawable.ic_menu_compass)
    builder.setOngoing(True)

    notification = builder.build()
    startForeground(1, notification)
except Exception:
    pass

while True:
    time.sleep(60)
