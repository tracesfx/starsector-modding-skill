package tlc.combat;

import com.fs.starfarer.api.combat.CombatEngineAPI;
import com.fs.starfarer.api.combat.CombatEntityAPI;
import com.fs.starfarer.api.combat.DamageType;
import com.fs.starfarer.api.combat.DamagingProjectileAPI;
import com.fs.starfarer.api.combat.OnHitEffectPlugin;
import com.fs.starfarer.api.combat.ShipAPI;
import com.fs.starfarer.api.combat.listeners.ApplyDamageResultAPI;
import org.lwjgl.util.vector.Vector2f;

/** Foreclosure Battery: +50% damage (as a follow-up energy hit) against ships at or above 50% flux. */
public class TLCForeclosureOnHit implements OnHitEffectPlugin {
    public static final float FLUX_THRESHOLD = 0.5f;
    public static final float BONUS = 0.5f;

    @Override
    public void onHit(DamagingProjectileAPI projectile, CombatEntityAPI target, Vector2f point, boolean shieldHit,
                      ApplyDamageResultAPI damageResult, CombatEngineAPI engine) {
        if (engine == null || projectile == null || point == null || !(target instanceof ShipAPI)) return;
        ShipAPI ship = (ShipAPI) target;
        if (ship.isHulk() || !ship.isAlive() || ship.getFluxTracker() == null) return;
        if (ship.getFluxLevel() < FLUX_THRESHOLD) return;
        float bonus = projectile.getDamageAmount() * BONUS;
        if (bonus <= 0f) return;
        engine.applyDamage(ship, point, bonus, DamageType.ENERGY, 0f, false, false, projectile.getSource(), true);
        engine.addHitParticle(point, ship.getVelocity(), 110f, 1f, 0.35f, TLCLedgerPlugin.JADE);
        engine.addFloatingText(point, "FORECLOSED", 20f, TLCLedgerPlugin.JADE, ship, 0.3f, 0.6f);
    }
}
