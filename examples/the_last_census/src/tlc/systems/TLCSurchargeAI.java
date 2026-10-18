package tlc.systems;

import com.fs.starfarer.api.combat.CombatEngineAPI;
import com.fs.starfarer.api.combat.ShipAPI;
import com.fs.starfarer.api.combat.ShipSystemAIScript;
import com.fs.starfarer.api.combat.ShipSystemAPI;
import com.fs.starfarer.api.combat.ShipwideAIFlags;
import com.fs.starfarer.api.util.IntervalUtil;
import com.fs.starfarer.api.util.Misc;
import org.lwjgl.util.vector.Vector2f;

/** Fires Surcharge when enough hostile tonnage (weighted up for ships already under flux pressure) is in range. */
public class TLCSurchargeAI implements ShipSystemAIScript {
    private ShipAPI ship;
    private ShipSystemAPI system;
    private CombatEngineAPI engine;
    private final IntervalUtil tracker = new IntervalUtil(0.4f, 0.6f);

    @Override
    public void init(ShipAPI ship, ShipSystemAPI system, ShipwideAIFlags flags, CombatEngineAPI engine) {
        this.ship = ship;
        this.system = system;
        this.engine = engine;
    }

    @Override
    public void advance(float amount, Vector2f missileDangerDir, Vector2f collisionDangerDir, ShipAPI target) {
        if (ship == null || system == null || engine == null) return;
        tracker.advance(amount);
        if (!tracker.intervalElapsed()) return;
        if (system.isActive() || system.isCoolingDown() || system.isOutOfAmmo()) return;
        if (ship.getFluxTracker().isOverloadedOrVenting()) return;
        if (ship.getFluxTracker().getMaxFlux() - ship.getFluxTracker().getCurrFlux() < system.getFluxPerUse()) return;
        float range = TLCSurchargeStats.getRange(ship);
        float weight = 0f;
        for (ShipAPI s : engine.getShips()) {
            if (s.isFighter() || s.isHulk() || !s.isAlive() || s.getOwner() == ship.getOwner()) continue;
            if (Misc.getDistance(ship.getLocation(), s.getLocation()) - s.getCollisionRadius() > range) continue;
            float w;
            switch (s.getHullSize()) {
                case CAPITAL_SHIP: w = 4f; break;
                case CRUISER: w = 3f; break;
                case DESTROYER: w = 2f; break;
                default: w = 1f; break;
            }
            if (s.getFluxLevel() > 0.4f) w += 1f;
            if (s.getShield() != null && s.getShield().isOn()) w += 0.5f;
            weight += w;
        }
        if (weight >= 3.5f || (weight >= 2f && ship.getFluxLevel() < 0.4f)) {
            ship.useSystem();
        }
    }
}
