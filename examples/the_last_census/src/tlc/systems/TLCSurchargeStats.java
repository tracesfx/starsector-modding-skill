package tlc.systems;

import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.combat.CombatEngineAPI;
import com.fs.starfarer.api.combat.MutableShipStatsAPI;
import com.fs.starfarer.api.combat.ShipAPI;
import com.fs.starfarer.api.impl.combat.BaseShipSystemScript;
import com.fs.starfarer.api.util.Misc;
import org.lwjgl.util.vector.Vector2f;
import tlc.combat.TLCLedgerPlugin;

/**
 * Surcharge: while active, hostile ships in range pay +35% flux to fire weapons and take +15% shield damage.
 * The debuff itself is owned by TLCLedgerPlugin with a short refreshing timer, so it always expires even if
 * this ship dies mid-activation.
 */
public class TLCSurchargeStats extends BaseShipSystemScript {
    public static final float RANGE_SMALL = 800f;
    public static final float RANGE_LARGE = 1000f;
    private static final float REFRESH = 0.25f;

    private boolean pulsed = false;

    public static float getRange(ShipAPI ship) {
        if (ship != null && (ship.isCruiser() || ship.isCapital())) return RANGE_LARGE;
        return RANGE_SMALL;
    }

    @Override
    public void apply(MutableShipStatsAPI stats, String id, State state, float effectLevel) {
        if (!(stats.getEntity() instanceof ShipAPI)) return;
        ShipAPI ship = (ShipAPI) stats.getEntity();
        CombatEngineAPI engine = Global.getCombatEngine();
        if (engine == null || effectLevel <= 0f) return;
        TLCLedgerPlugin ledger = TLCLedgerPlugin.get();
        if (ledger == null) return;
        float range = getRange(ship);
        if (!pulsed) {
            pulsed = true;
            pulse(engine, ship, range);
        }
        for (ShipAPI s : engine.getShips()) {
            if (s == ship || s.isFighter() || s.isHulk() || !s.isAlive()) continue;
            if (s.getOwner() == ship.getOwner()) continue;
            if (Misc.getDistance(ship.getLocation(), s.getLocation()) - s.getCollisionRadius() > range) continue;
            ledger.refreshDebuff(s, TLCLedgerPlugin.Debuff.SURCHARGE, REFRESH, effectLevel);
        }
    }

    private static void pulse(CombatEngineAPI engine, ShipAPI ship, float range) {
        Vector2f c = ship.getLocation();
        for (int i = 0; i < 32; i++) {
            float a = (float) (i * Math.PI * 2.0 / 32.0);
            Vector2f p = new Vector2f(c.x + (float) Math.cos(a) * range * 0.95f, c.y + (float) Math.sin(a) * range * 0.95f);
            Vector2f v = new Vector2f((float) Math.cos(a) * 25f, (float) Math.sin(a) * 25f);
            engine.addHitParticle(p, v, 45f, 0.5f, 0.8f, TLCLedgerPlugin.JADE);
        }
    }

    @Override
    public void unapply(MutableShipStatsAPI stats, String id) {
        pulsed = false;
    }

    @Override
    public StatusData getStatusData(int index, State state, float effectLevel) {
        if (index == 0) return new StatusData("surcharging hostile fire control", false);
        return null;
    }
}
