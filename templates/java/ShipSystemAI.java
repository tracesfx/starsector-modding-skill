package {{PACKAGE}};

import com.fs.starfarer.api.combat.CombatEngineAPI;
import com.fs.starfarer.api.combat.ShipAPI;
import com.fs.starfarer.api.combat.ShipSystemAIScript;
import com.fs.starfarer.api.combat.ShipSystemAPI;
import com.fs.starfarer.api.combat.ShipwideAIFlags;
import com.fs.starfarer.api.util.IntervalUtil;
import com.fs.starfarer.api.util.Misc;
import org.lwjgl.util.vector.Vector2f;

/**
 * Custom AI for ship system "{{NAME}}": the .system file needs "aiType":"CUSTOM" and "aiScript":"{{PACKAGE}}.{{CLASS}}".
 * Decide a few times per second (IntervalUtil), not every frame, and only call useSystem() when the system can fire.
 */
public class {{CLASS}} implements ShipSystemAIScript {
    private static final float USE_RANGE = 900f;
    private ShipAPI ship;
    private ShipSystemAPI system;
    private final IntervalUtil tracker = new IntervalUtil(0.35f, 0.55f);

    @Override
    public void init(ShipAPI ship, ShipSystemAPI system, ShipwideAIFlags flags, CombatEngineAPI engine) {
        this.ship = ship;
        this.system = system;
    }

    @Override
    public void advance(float amount, Vector2f missileDangerDir, Vector2f collisionDangerDir, ShipAPI target) {
        if (ship == null || system == null || !ship.isAlive()) return;
        tracker.advance(amount);
        if (!tracker.intervalElapsed()) return;
        if (system.isActive() || system.getCooldownRemaining() > 0f || system.isOutOfAmmo() || ship.getFluxTracker().isOverloadedOrVenting()) return;
        if (target == null || !target.isAlive()) return;
        if (ship.getFluxLevel() > 0.75f) return;
        if (Misc.getDistance(ship.getLocation(), target.getLocation()) > USE_RANGE + target.getCollisionRadius()) return;
        ship.useSystem();
    }
}
