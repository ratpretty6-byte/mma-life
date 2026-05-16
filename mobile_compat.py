try:
    from android import mActivity
    from jnius import autoclass
    ANDROID = True
except ImportError:
    ANDROID = False

def get_screen_density() -> float:
    if not ANDROID:
        return 1.0
    DisplayMetrics = autoclass('android.util.DisplayMetrics')
    metrics = DisplayMetrics()
    mActivity.getWindowManager().getDefaultDisplay().getMetrics(metrics)
    return metrics.density

def optimize_memory():
    if ANDROID:
        # Suggest garbage collection
        import gc
        gc.collect()

def request_storage_permissions():
    if not ANDROID:
        return
    # Android runtime permission check
    pass

def set_keep_screen_on(enabled: bool = True):
    if not ANDROID:
        return
    WindowManager = autoclass('android.view.WindowManager$LayoutParams')
    activity = mActivity
    window = activity.getWindow()
    if enabled:
        window.addFlags(WindowManager.FLAG_KEEP_SCREEN_ON)
    else:
        window.clearFlags(WindowManager.FLAG_KEEP_SCREEN_ON)
