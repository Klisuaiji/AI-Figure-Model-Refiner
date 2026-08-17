import bpy
import time
import traceback


class Logger:
    """Centralised logger. Writes to stdout and mirrors into the UI log
    collection ``bpy.types.Scene.afr_log`` when available."""

    MAX_LINES = 500

    def __init__(self, name="AFR"):
        self.name = name

    def _push_scene(self, level, text):
        try:
            sc = bpy.context.scene
            if not hasattr(sc, "afr_log"):
                return
            item = sc.afr_log.add()
            item.level = level
            item.text = text
            item.time = time.strftime("%H:%M:%S")
            # cap the log size
            while len(sc.afr_log) > self.MAX_LINES:
                sc.afr_log.remove(0)
        except (AttributeError, TypeError, KeyError):
            # scene / property not ready; safe to ignore during early
            # register() or during scene reload.
            pass
        except Exception as e:
            # unexpected — print once but never propagate (the logger
            # must never raise, that would crash the calling operator).
            traceback.print_exc()
            print("[AFR logger internal] %s" % e)

    def log(self, level, text):
        line = "[%s] %s" % (level, text)
        print("%s %s" % (self.name, line))
        self._push_scene(level, text)
        return line

    def debug(self, t):
        return self.log("DEBUG", t)

    def info(self, t):
        return self.log("INFO", t)

    def warning(self, t):
        return self.log("WARNING", t)

    def error(self, t):
        return self.log("ERROR", t)


logger = Logger()