package {{PACKAGE}};

import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.combat.BaseEveryFrameCombatPlugin;
import com.fs.starfarer.api.combat.CombatEngineAPI;
import com.fs.starfarer.api.combat.ShipAPI;
import com.fs.starfarer.api.input.InputEventAPI;
import com.fs.starfarer.api.util.IntervalUtil;
import org.apache.log4j.Logger;

import java.util.ArrayList;
import java.util.List;

/**
 * Every-frame combat plugin "{{NAME}}". Register it in data/config/settings.json:
 *     "plugins": { "{{PREFIX}}{{CLASS}}": "{{PACKAGE}}.{{CLASS}}" }
 * (vanilla registers its own combat plugins there, and so do MagicLib, GraphicsLib, LunaLib and Console Commands).
 * The engine creates one instance per battle and calls init(engine) first.
 *
 * Performance rules for code that runs every frame: return early when paused, do periodic work on an IntervalUtil,
 * reuse preallocated lists (clear() instead of new), avoid lambdas/iterators/String building in advance().
 * Share per-battle state through engine.getCustomData(), never through static fields (they outlive the battle).
 */
public class {{CLASS}} extends BaseEveryFrameCombatPlugin {
    private static final Logger log = Global.getLogger({{CLASS}}.class);
    public static final String DATA_KEY = "{{PREFIX}}{{CLASS}}";

    private CombatEngineAPI engine;
    private final IntervalUtil interval = new IntervalUtil(0.25f, 0.25f);
    private final List<ShipAPI> scratch = new ArrayList<ShipAPI>(64);
    private boolean failed = false;

    @Override
    public void init(CombatEngineAPI engine) {
        this.engine = engine;
        if (engine != null) engine.getCustomData().put(DATA_KEY, this);
    }

    /** The running instance for the current battle, or null. */
    public static {{CLASS}} get() {
        CombatEngineAPI e = Global.getCombatEngine();
        if (e == null) return null;
        Object o = e.getCustomData().get(DATA_KEY);
        return o instanceof {{CLASS}} ? ({{CLASS}}) o : null;
    }

    @Override
    public void advance(float amount, List<InputEventAPI> events) {
        if (engine == null || failed || engine.isPaused()) return;
        try {
            interval.advance(amount);
            if (!interval.intervalElapsed()) return;
            scratch.clear();
            List<ShipAPI> ships = engine.getShips();
            for (int i = 0, n = ships.size(); i < n; i++) {
                ShipAPI s = ships.get(i);
                if (s == null || !s.isAlive() || s.isHulk() || s.isFighter()) continue;
                scratch.add(s);
            }
            // ... periodic logic over `scratch` ...
        } catch (Throwable t) {
            failed = true; // one bad frame must not crash the battle or spam the log every frame
            log.error("{{CLASS}} disabled for this battle after an error", t);
        }
    }
}
