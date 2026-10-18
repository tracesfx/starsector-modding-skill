package {{PACKAGE}};

import com.fs.starfarer.api.combat.MutableShipStatsAPI;
import com.fs.starfarer.api.impl.combat.BaseShipSystemScript;

/**
 * Ship system "{{NAME}}" stats script: the .system file's "statsScript" is {{PACKAGE}}.{{CLASS}}.
 *
 * State runs IDLE -> IN (effectLevel 0..1) -> ACTIVE (1) -> OUT (1..0) -> COOLDOWN (wiki tidbit). apply() is called
 * every frame while the system is not idle; unapply() once when it ends. Always remove in unapply() exactly what
 * apply() added, keyed by the `id` argument, or the bonus sticks for the rest of the battle.
 */
public class {{CLASS}} extends BaseShipSystemScript {
    public static final float DAMAGE_BONUS_PERCENT = 25f;
    public static final float FLUX_COST_PERCENT = 15f;

    @Override
    public void apply(MutableShipStatsAPI stats, String id, State state, float effectLevel) {
        stats.getEnergyWeaponDamageMult().modifyPercent(id, DAMAGE_BONUS_PERCENT * effectLevel);
        stats.getBallisticWeaponDamageMult().modifyPercent(id, DAMAGE_BONUS_PERCENT * effectLevel);
        stats.getEnergyWeaponFluxCostMod().modifyPercent(id, FLUX_COST_PERCENT * effectLevel);
        stats.getBallisticWeaponFluxCostMod().modifyPercent(id, FLUX_COST_PERCENT * effectLevel);
    }

    @Override
    public void unapply(MutableShipStatsAPI stats, String id) {
        stats.getEnergyWeaponDamageMult().unmodify(id);
        stats.getBallisticWeaponDamageMult().unmodify(id);
        stats.getEnergyWeaponFluxCostMod().unmodify(id);
        stats.getBallisticWeaponFluxCostMod().unmodify(id);
    }

    @Override
    public StatusData getStatusData(int index, State state, float effectLevel) {
        if (index == 0) return new StatusData("+" + Math.round(DAMAGE_BONUS_PERCENT * effectLevel) + "% weapon damage", false);
        if (index == 1) return new StatusData("+" + Math.round(FLUX_COST_PERCENT * effectLevel) + "% weapon flux cost", true);
        return null;
    }
}
