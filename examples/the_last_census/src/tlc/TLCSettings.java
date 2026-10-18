package tlc;

import com.fs.starfarer.api.Global;
import lunalib.lunaSettings.LunaSettings;
import org.apache.log4j.Logger;

/** LunaLib-backed settings with safe defaults if a value is missing or LunaLib misbehaves. */
public final class TLCSettings {
    private static final Logger log = Global.getLogger(TLCSettings.class);

    private TLCSettings() {
    }

    public static boolean auditsEnabled() {
        try {
            Boolean b = LunaSettings.getBoolean(TLCIds.MOD_ID, TLCIds.LUNA_ENABLE_AUDITS);
            return b == null || b;
        } catch (Throwable t) {
            log.warn("TLC: could not read setting " + TLCIds.LUNA_ENABLE_AUDITS + ", using default", t);
            return true;
        }
    }

    public static int maxAssessorFleets() {
        try {
            Integer i = LunaSettings.getInt(TLCIds.MOD_ID, TLCIds.LUNA_MAX_ASSESSORS);
            if (i == null) return 3;
            return Math.max(0, Math.min(6, i));
        } catch (Throwable t) {
            log.warn("TLC: could not read setting " + TLCIds.LUNA_MAX_ASSESSORS + ", using default", t);
            return 3;
        }
    }
}
