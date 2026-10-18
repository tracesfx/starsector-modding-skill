package {{PACKAGE}};

import com.fs.starfarer.api.combat.BaseHullMod;
import com.fs.starfarer.api.combat.MutableShipStatsAPI;
import com.fs.starfarer.api.combat.ShipAPI;
import com.fs.starfarer.api.combat.ShipAPI.HullSize;

/**
 * Hullmod "{{NAME}}" (hull_mods.csv id {{ID}}). Register it with a hull_mods.csv row whose "script" column is
 * {{PACKAGE}}.{{CLASS}}; the "desc" column text uses %s for each getDescriptionParam index.
 *
 * Call order (wiki "Hullmod code call-order"): applyEffectsBeforeShipCreation (stats; the only place stat changes
 * reach the campaign layer and the refit/codex stat cards) -> applyEffectsAfterShipCreation (the ShipAPI exists:
 * weapons, wings, listeners) -> advanceInCombat every frame. Changing hullmods inside these restarts ship creation.
 * modifyPercent bonuses add together; modifyMult bonuses multiply (wiki tidbit).
 */
public class {{CLASS}} extends BaseHullMod {
    public static final float ARMOR_BONUS_PERCENT = 10f;
    public static final float SPEED_PENALTY_PERCENT = 5f;

    @Override
    public void applyEffectsBeforeShipCreation(HullSize hullSize, MutableShipStatsAPI stats, String id) {
        stats.getArmorBonus().modifyPercent(id, ARMOR_BONUS_PERCENT);
        stats.getMaxSpeed().modifyPercent(id, -SPEED_PENALTY_PERCENT);
    }

    @Override
    public void applyEffectsAfterShipCreation(ShipAPI ship, String id) {
        // Per-ship setup that needs the ShipAPI (e.g. ship.addListener(...)). Keep stat changes out of here.
    }

    @Override
    public void advanceInCombat(ShipAPI ship, float amount) {
        if (ship == null || !ship.isAlive()) return;
        // Runs every frame for every ship with the hullmod: no allocations, no expensive lookups here.
    }

    @Override
    public String getDescriptionParam(int index, HullSize hullSize) {
        if (index == 0) return Math.round(ARMOR_BONUS_PERCENT) + "%";
        if (index == 1) return Math.round(SPEED_PENALTY_PERCENT) + "%";
        return null;
    }

    @Override
    public boolean isApplicableToShip(ShipAPI ship) {
        return ship != null && !ship.isFighter();
    }

    @Override
    public String getUnapplicableReason(ShipAPI ship) {
        return "Cannot be installed on fighters";
    }
}
