package {{PACKAGE}};

import com.fs.starfarer.api.combat.CombatEngineAPI;
import com.fs.starfarer.api.combat.DamagingProjectileAPI;
import com.fs.starfarer.api.combat.EveryFrameWeaponEffectPlugin;
import com.fs.starfarer.api.combat.OnFireEffectPlugin;
import com.fs.starfarer.api.combat.WeaponAPI;

/**
 * Weapon effect "{{NAME}}": the .wpn file's "everyFrameEffect" (and/or "onFireEffect") is {{PACKAGE}}.{{CLASS}}.
 * The engine makes one instance PER WEAPON for everyFrameEffect, so per-weapon state in fields is fine here.
 * Example: count shots and brighten the weapon glow as it heats up; cool down while idle.
 */
public class {{CLASS}} implements EveryFrameWeaponEffectPlugin, OnFireEffectPlugin {
    private static final float HEAT_PER_SHOT = 0.15f;
    private static final float COOL_PER_SECOND = 0.4f;
    private float heat = 0f;

    @Override
    public void advance(float amount, CombatEngineAPI engine, WeaponAPI weapon) {
        if (engine == null || weapon == null || engine.isPaused()) return;
        heat = Math.max(0f, heat - COOL_PER_SECOND * amount);
        if (weapon.getGlowSpriteAPI() != null) weapon.getGlowSpriteAPI().setAlphaMult(Math.min(1f, heat));
    }

    @Override
    public void onFire(DamagingProjectileAPI projectile, WeaponAPI weapon, CombatEngineAPI engine) {
        heat = Math.min(1f, heat + HEAT_PER_SHOT);
    }
}
