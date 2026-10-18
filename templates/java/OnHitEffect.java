package {{PACKAGE}};

import com.fs.starfarer.api.combat.CombatEngineAPI;
import com.fs.starfarer.api.combat.CombatEntityAPI;
import com.fs.starfarer.api.combat.DamageType;
import com.fs.starfarer.api.combat.DamagingProjectileAPI;
import com.fs.starfarer.api.combat.OnHitEffectPlugin;
import com.fs.starfarer.api.combat.ShipAPI;
import com.fs.starfarer.api.combat.listeners.ApplyDamageResultAPI;
import org.lwjgl.util.vector.Vector2f;

import java.awt.Color;

/**
 * On-hit effect "{{NAME}}": the .proj file's "onHitEffect" is {{PACKAGE}}.{{CLASS}} (one shared instance serves every
 * projectile, so keep no per-shot state in fields). Example: a small EMP arc when the shot hits hull or armour.
 */
public class {{CLASS}} implements OnHitEffectPlugin {
    private static final float ARC_DAMAGE = 50f;
    private static final float ARC_EMP = 150f;
    private static final Color CORE = new Color(255, 255, 255, 255);
    private static final Color FRINGE = new Color(120, 180, 255, 255);

    @Override
    public void onHit(DamagingProjectileAPI projectile, CombatEntityAPI target, Vector2f point, boolean shieldHit,
                      ApplyDamageResultAPI damageResult, CombatEngineAPI engine) {
        if (shieldHit || engine == null || !(target instanceof ShipAPI) || projectile == null) return;
        ShipAPI ship = (ShipAPI) target;
        if (!ship.isAlive() || ship.isHulk()) return;
        engine.spawnEmpArc(projectile.getSource(), point, ship, ship, DamageType.ENERGY, ARC_DAMAGE, ARC_EMP,
                10000f, "tachyon_lance_emp_impact", 20f, FRINGE, CORE);
    }
}
