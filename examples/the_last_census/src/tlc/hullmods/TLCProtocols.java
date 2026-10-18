package tlc.hullmods;

import com.fs.starfarer.api.combat.BaseHullMod;
import com.fs.starfarer.api.combat.ShipAPI;
import com.fs.starfarer.api.combat.ShipAPI.HullSize;
import tlc.combat.TLCLedgerPlugin;

/** Assessor Protocols (built into Bureau hulls): Lien and Settlement. All bookkeeping lives in TLCLedgerPlugin. */
public class TLCProtocols extends BaseHullMod {

    @Override
    public void advanceInCombat(ShipAPI ship, float amount) {
        if (ship == null || !ship.isAlive() || ship.isHulk()) return;
        TLCLedgerPlugin ledger = TLCLedgerPlugin.get();
        if (ledger != null) ledger.registerLienholder(ship);
    }

    @Override
    public String getDescriptionParam(int index, HullSize hullSize) {
        if (index == 0) return Math.round(TLCLedgerPlugin.SETTLE_FRACTION * 100f) + "%";
        if (index == 1) return Math.round(TLCLedgerPlugin.SETTLE_CAP * 100f) + "%";
        return null;
    }
}
