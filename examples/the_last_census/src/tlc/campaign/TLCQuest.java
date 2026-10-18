package tlc.campaign;

import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.campaign.CampaignFleetAPI;
import com.fs.starfarer.api.campaign.CargoAPI;
import com.fs.starfarer.api.campaign.FleetAssignment;
import com.fs.starfarer.api.campaign.RepLevel;
import com.fs.starfarer.api.campaign.SectorEntityToken;
import com.fs.starfarer.api.campaign.SpecialItemData;
import com.fs.starfarer.api.campaign.StarSystemAPI;
import com.fs.starfarer.api.campaign.TextPanelAPI;
import com.fs.starfarer.api.campaign.rules.MemoryAPI;
import com.fs.starfarer.api.fleet.FleetMemberAPI;
import com.fs.starfarer.api.fleet.FleetMemberType;
import com.fs.starfarer.api.impl.campaign.CoreReputationPlugin.CustomRepImpact;
import com.fs.starfarer.api.impl.campaign.CoreReputationPlugin.RepActionEnvelope;
import com.fs.starfarer.api.impl.campaign.CoreReputationPlugin.RepActions;
import com.fs.starfarer.api.impl.campaign.fleets.FleetFactoryV3;
import com.fs.starfarer.api.impl.campaign.fleets.FleetParamsV3;
import com.fs.starfarer.api.impl.campaign.ids.Factions;
import com.fs.starfarer.api.impl.campaign.ids.FleetTypes;
import com.fs.starfarer.api.impl.campaign.ids.MemFlags;
import com.fs.starfarer.api.impl.campaign.rulecmd.AddRemoveCommodity;
import com.fs.starfarer.api.impl.campaign.rulecmd.AddShip;
import com.fs.starfarer.api.util.Misc;
import org.apache.log4j.Logger;
import org.lwjgl.util.vector.Vector2f;
import tlc.TLCIds;
import tlc.world.TLCWorldGen;

import java.util.Random;

/** Quest-stage transitions, the relay salvage gang, and rewards. */
public final class TLCQuest {
    private static final Logger log = Global.getLogger(TLCQuest.class);
    private static final String MEM_PIRATES_SPAWNED = "$tlc_relayPiratesSpawned";

    private TLCQuest() {
    }

    public static void advance() {
        if (TLCIds.STAGE_RELAY.equals(TLCMem.stage()) && !TLCMem.flag(TLCIds.MEM_RELAY_ACTIVE)
                && !TLCMem.flag(MEM_PIRATES_SPAWNED)) {
            spawnRelayPirates();
        }
    }

    public static void setStage(String stage, TextPanelAPI panel) {
        TLCMem.setString(TLCIds.MEM_STAGE, stage);
        if (TLCIds.STAGE_DONE.equals(stage)) TLCWorldGen.releaseTallyhouse(TLCMem.tallyhouseMarket());
        TLCCensusIntel.update(stage, panel);
    }

    // ------------------------------------------------------------------------------------ relay salvagers
    public static void spawnRelayPirates() {
        try {
            StarSystemAPI envoi = Global.getSector().getStarSystem(TLCIds.ID_SYSTEM_ENVOI);
            SectorEntityToken relay = TLCMem.relay();
            if (envoi == null || relay == null) return;
            float playerFP = Global.getSector().getPlayerFleet() != null
                    ? Global.getSector().getPlayerFleet().getFleetPoints() : 60f;
            float combat = Math.max(50f, Math.min(180f, playerFP * 0.8f));
            FleetParamsV3 params = new FleetParamsV3(null, envoi.getLocation(), Factions.PIRATES, null,
                    FleetTypes.PATROL_MEDIUM, combat, 0f, 0f, 0f, 0f, 0f, 0f);
            params.random = new Random();
            CampaignFleetAPI fleet = FleetFactoryV3.createFleet(params);
            if (fleet == null || fleet.getFleetData().getNumMembers() <= 0) return;
            fleet.setName("Relay Salvage Gang");
            fleet.setNoFactionInName(true);
            MemoryAPI mem = fleet.getMemoryWithoutUpdate();
            mem.set(TLCIds.MEM_RELAY_PIRATES, true);
            Misc.setFlagWithReason(mem, MemFlags.MEMORY_KEY_MAKE_AGGRESSIVE, "tlc_relay", true, -1f);
            Misc.setFlagWithReason(mem, MemFlags.MEMORY_KEY_MAKE_HOSTILE, "tlc_relay", true, -1f);
            Misc.setFlagWithReason(mem, MemFlags.MEMORY_KEY_LOW_REP_IMPACT, "tlc_relay", true, -1f);
            Misc.makeImportant(fleet, "tlc_relay");
            fleet.setNoAutoDespawn(true);
            envoi.addEntity(fleet);
            Vector2f p = Misc.getPointAtRadius(relay.getLocation(), 350f);
            fleet.setLocation(p.x, p.y);
            fleet.addAssignment(FleetAssignment.ORBIT_AGGRESSIVE, relay, 1000000f, "stripping the courier relay");
            TLCMem.setFlag(MEM_PIRATES_SPAWNED, true);
        } catch (Throwable t) {
            log.error("TLC: could not spawn the relay salvagers", t);
            TLCMem.setFlag(MEM_PIRATES_SPAWNED, true); // never retry in a loop
        }
    }

    /** True when no salvage-gang fleet remains in the Envoi system. */
    public static boolean relayClear() {
        StarSystemAPI envoi = Global.getSector().getStarSystem(TLCIds.ID_SYSTEM_ENVOI);
        if (envoi == null) return true;
        for (CampaignFleetAPI f : envoi.getFleets()) {
            if (f != null && f.isAlive() && f.getMemoryWithoutUpdate().getBoolean(TLCIds.MEM_RELAY_PIRATES)) return false;
        }
        return true;
    }

    // ------------------------------------------------------------------------------------ rewards
    public static void adjustRep(float delta, RepLevel limit, TextPanelAPI panel) {
        CustomRepImpact impact = new CustomRepImpact();
        impact.delta = delta;
        impact.limit = limit;
        Global.getSector().adjustPlayerReputation(
                new RepActionEnvelope(RepActions.CUSTOM, impact, null, panel, true), TLCIds.FACTION_BUREAU);
    }

    public static void giveShip(String variantId, String name, TextPanelAPI panel) {
        FleetMemberAPI m = Global.getFactory().createFleetMember(FleetMemberType.SHIP, variantId);
        if (m == null) return;
        m.setShipName(name);
        m.getRepairTracker().setCR(m.getRepairTracker().getMaxCR());
        Global.getSector().getPlayerFleet().getFleetData().addFleetMember(m);
        if (panel != null) AddShip.addShipGainText(m, panel);
    }

    public static void giveCredits(int credits, TextPanelAPI panel) {
        Global.getSector().getPlayerFleet().getCargo().getCredits().add(credits);
        if (panel != null) AddRemoveCommodity.addCreditsGainText(credits, panel);
    }

    public static void giveBlueprints(TextPanelAPI panel) {
        CargoAPI cargo = Global.getSector().getPlayerFleet().getCargo();
        SpecialItemData data = new SpecialItemData(TLCIds.ITEM_BUREAU_PACKAGE, null);
        cargo.addSpecial(data, 1);
        if (panel != null) AddRemoveCommodity.addItemGainText(data, 1, panel);
    }

    public static void giveWeapons(String weaponId, int count, TextPanelAPI panel) {
        Global.getSector().getPlayerFleet().getCargo().addWeapons(weaponId, count);
        if (panel != null) AddRemoveCommodity.addWeaponGainText(weaponId, count, panel);
    }

    /** Ending A: "No. The Domain is gone." The audit closes; the charter archive is released. */
    public static void endArchived(TextPanelAPI panel) {
        TLCMem.setString(TLCIds.MEM_ENDING, TLCIds.ENDING_ARCHIVED);
        TLCMem.setFlag(TLCIds.MEM_AUDITS_ENDED, true);
        TLCMem.setFlag(TLCIds.MEM_ENUMERATOR, false);
        giveBlueprints(panel);
        giveShip(TLCIds.VARIANT_MAGISTRATE, "DBV Countersigned", panel);
        adjustRep(0.3f, RepLevel.COOPERATIVE, panel);
        setStage(TLCIds.STAGE_DONE, panel);
    }

    /** Ending B: "Someone will be. Keep counting." The audit continues; the player becomes Commissioner. */
    public static void endContinuing(TextPanelAPI panel) {
        TLCMem.setString(TLCIds.MEM_ENDING, TLCIds.ENDING_CONTINUING);
        TLCMem.setFlag(TLCIds.MEM_COMMISSIONER, true);
        giveShip(TLCIds.VARIANT_EXCHEQUER, "DBV Close of Accounts", panel);
        giveCredits(100000, panel);
        adjustRep(0.3f, RepLevel.COOPERATIVE, panel);
        setStage(TLCIds.STAGE_DONE, panel);
    }
}
