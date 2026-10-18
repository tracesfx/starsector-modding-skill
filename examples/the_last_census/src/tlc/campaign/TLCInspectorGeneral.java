package tlc.campaign;

import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.campaign.BattleAPI;
import com.fs.starfarer.api.campaign.CampaignEventListener.FleetDespawnReason;
import com.fs.starfarer.api.campaign.CampaignFleetAPI;
import com.fs.starfarer.api.campaign.FleetAssignment;
import com.fs.starfarer.api.campaign.LocationAPI;
import com.fs.starfarer.api.campaign.SectorEntityToken;
import com.fs.starfarer.api.campaign.econ.MarketAPI;
import com.fs.starfarer.api.campaign.rules.MemoryAPI;
import com.fs.starfarer.api.characters.FullName;
import com.fs.starfarer.api.characters.ImportantPeopleAPI;
import com.fs.starfarer.api.characters.PersonAPI;
import com.fs.starfarer.api.combat.ShipVariantAPI;
import com.fs.starfarer.api.fleet.FleetMemberAPI;
import com.fs.starfarer.api.impl.campaign.fleets.FleetFactoryV3;
import com.fs.starfarer.api.impl.campaign.ids.MemFlags;
import com.fs.starfarer.api.impl.campaign.ids.Personalities;
import com.fs.starfarer.api.impl.campaign.ids.Ranks;
import com.fs.starfarer.api.impl.campaign.ids.Skills;
import com.fs.starfarer.api.impl.campaign.ids.Tags;
import com.fs.starfarer.api.loading.VariantSource;
import com.fs.starfarer.api.util.Misc;
import org.apache.log4j.Logger;
import org.lwjgl.util.vector.Vector2f;
import tlc.TLCIds;

/**
 * The hidden Inspector-General. Triggered when the player tells three different audits that the Domain
 * is gone. The IG holds a "hearing" (a battle); defeating its flagship is the only evidence it accepts.
 */
public final class TLCInspectorGeneral {
    private static final Logger log = Global.getLogger(TLCInspectorGeneral.class);
    private static final String REASON = "tlc_hearing";
    private static final float WAIT_RADIUS = 350f;

    private TLCInspectorGeneral() {
    }

    public static void advance() {
        String s = TLCMem.igState();
        if (TLCIds.IG_REFERRED.equals(s)) {
            trySpawnNearPlayer();
        } else if (TLCIds.IG_DISPATCHED.equals(s)) {
            maintainPursuit();
        } else if (TLCIds.IG_WAITING.equals(s)) {
            ensureWaitingFleet();
        }
    }

    public static CampaignFleetAPI findFleet() {
        TLCHearingIntel intel = TLCHearingIntel.get();
        if (intel == null) return null;
        CampaignFleetAPI f = intel.getFleetRef();
        if (f == null || !f.isAlive()) return null;
        return f;
    }

    private static void trySpawnNearPlayer() {
        CampaignFleetAPI player = Global.getSector().getPlayerFleet();
        if (player == null || player.isInHyperspace() || player.isInHyperspaceTransition()) return;
        if (player.getContainingLocation() == null) return;
        if (Global.getSector().getCampaignUI() != null && Global.getSector().getCampaignUI().isShowingDialog()) return;
        if (TLCMem.bureau() == null || TLCMem.bureau().isHostileTo(player.getFaction())) return;
        if (!TLCMem.tallyhouseIntact()) return;

        CampaignFleetAPI fleet = findFleet();
        if (fleet == null) fleet = createFleet();
        if (fleet == null) return;
        LocationAPI loc = player.getContainingLocation();
        if (fleet.getContainingLocation() != loc) {
            if (fleet.getContainingLocation() != null) fleet.getContainingLocation().removeEntity(fleet);
            loc.addEntity(fleet);
            Vector2f p = Misc.getPointAtRadius(player.getLocation(), 1700f);
            fleet.setLocation(p.x, p.y);
        }
        fleet.clearAssignments();
        fleet.addAssignment(FleetAssignment.INTERCEPT, player, 30f, "seeking a hearing");
        setPursuit(fleet, true);
        TLCMem.setString(TLCIds.MEM_IG_STATE, TLCIds.IG_DISPATCHED);

        TLCHearingIntel intel = TLCHearingIntel.get();
        if (intel == null) {
            intel = new TLCHearingIntel(fleet);
            intel.setImportant(true);
            Global.getSector().getIntelManager().addIntel(intel);
        } else {
            intel.setFleet(fleet);
            intel.sendUpdateIfPlayerHasIntel(null, false);
        }
    }

    private static void maintainPursuit() {
        CampaignFleetAPI f = findFleet();
        CampaignFleetAPI player = Global.getSector().getPlayerFleet();
        if (f == null) {
            TLCMem.setString(TLCIds.MEM_IG_STATE, TLCIds.IG_REFERRED);
            return;
        }
        if (player == null) return;
        if (f.getContainingLocation() != player.getContainingLocation()) {
            // The player left before the hearing: the Inspector-General goes home and waits.
            sendHomeToWait(f);
            return;
        }
        setPursuit(f, true);
    }

    /**
     * Where the IG holds session: the planet Docket (2400 su from the star, well clear of the corona, and at least
     * ~2500 su from the Tallyhouse, far outside its station support range). Falls back to the Tallyhouse.
     */
    private static SectorEntityToken waitAnchor() {
        SectorEntityToken docket = Global.getSector().getEntityById(TLCIds.ID_DOCKET);
        if (docket != null) return docket;
        return TLCMem.tallyhouse();
    }

    private static void ensureWaitingFleet() {
        CampaignFleetAPI f = findFleet();
        if (f != null) return;
        SectorEntityToken anchor = waitAnchor();
        if (anchor == null || !TLCMem.tallyhouseIntact()) return;
        f = createFleet();
        if (f == null) return;
        anchor.getContainingLocation().addEntity(f);
        Vector2f p = Misc.getPointAtRadius(anchor.getLocation(), WAIT_RADIUS);
        f.setLocation(p.x, p.y);
        f.addAssignment(FleetAssignment.ORBIT_PASSIVE, anchor, 1000000f, "holding session at Docket");
        TLCHearingIntel intel = TLCHearingIntel.get();
        if (intel != null) intel.setFleet(f);
    }

    public static void sendHomeToWait(CampaignFleetAPI f) {
        if (f == null) return;
        setPursuit(f, false);
        MemoryAPI mem = f.getMemoryWithoutUpdate();
        Misc.setFlagWithReason(mem, MemFlags.MEMORY_KEY_MAKE_HOSTILE, REASON, false, 0f);
        Misc.setFlagWithReason(mem, MemFlags.MEMORY_KEY_MAKE_AGGRESSIVE, REASON, false, 0f);
        f.clearAssignments();
        SectorEntityToken anchor = waitAnchor();
        if (anchor != null) {
            f.addAssignment(FleetAssignment.GO_TO_LOCATION, anchor, 200f, "returning to Docket");
            f.addAssignment(FleetAssignment.ORBIT_PASSIVE, anchor, 1000000f, "holding session at Docket");
        }
        TLCMem.setString(TLCIds.MEM_IG_STATE, TLCIds.IG_WAITING);
        TLCHearingIntel intel = TLCHearingIntel.get();
        if (intel != null) intel.sendUpdateIfPlayerHasIntel(null, false);
    }

    private static void setPursuit(CampaignFleetAPI f, boolean on) {
        MemoryAPI mem = f.getMemoryWithoutUpdate();
        Misc.setFlagWithReason(mem, MemFlags.MEMORY_KEY_PURSUE_PLAYER, REASON, on, 1.5f);
        Misc.setFlagWithReason(mem, MemFlags.MEMORY_KEY_STICK_WITH_PLAYER_IF_ALREADY_TARGET, REASON, on, 1.5f);
        // Exactly the flags vanilla's HasslePlayerScript uses (pursue, stick, busy, special action). Deliberately no
        // FLEET_IGNORES_OTHER_FLEETS: without FLEET_DO_NOT_IGNORE_PLAYER it would also make the IG ignore the player.
        Misc.setFlagWithReason(mem, MemFlags.FLEET_BUSY, REASON, on, 1.5f);
        if (on) {
            mem.set(MemFlags.FLEET_SPECIAL_ACTION, true, 1.5f);
        } else {
            mem.unset(MemFlags.FLEET_SPECIAL_ACTION);
        }
    }

    public static PersonAPI getOrCreateInspector() {
        ImportantPeopleAPI ip = Global.getSector().getImportantPeople();
        PersonAPI p = ip.getPerson(TLCIds.ID_INSPECTOR);
        if (p != null) return p;
        p = Global.getFactory().createPerson();
        p.setId(TLCIds.ID_INSPECTOR);
        p.setFaction(TLCIds.FACTION_BUREAU);
        p.setName(new FullName("Ismene", "Varga", FullName.Gender.FEMALE));
        p.setPortraitSprite(TLCIds.PORTRAIT_INSPECTOR);
        p.setRankId(Ranks.SPACE_ADMIRAL);
        p.setPostId(Ranks.POST_FLEET_COMMANDER);
        p.setPersonality(Personalities.STEADY);
        p.getStats().setLevel(7);
        p.getStats().setSkillLevel(Skills.FIELD_MODULATION, 2);
        p.getStats().setSkillLevel(Skills.TARGET_ANALYSIS, 2);
        p.getStats().setSkillLevel(Skills.SYSTEMS_EXPERTISE, 2);
        p.getStats().setSkillLevel(Skills.ENERGY_WEAPON_MASTERY, 1);
        p.getStats().setSkillLevel(Skills.GUNNERY_IMPLANTS, 1);
        p.getStats().setSkillLevel(Skills.DAMAGE_CONTROL, 1);
        p.getStats().setSkillLevel(Skills.POLARIZED_ARMOR, 1);
        ip.addPerson(p);
        return p;
    }

    private static CampaignFleetAPI createFleet() {
        try {
            MarketAPI home = TLCMem.tallyhouseMarket();
            CampaignFleetAPI fleet = FleetFactoryV3.createEmptyFleet(TLCIds.FACTION_BUREAU, TLCIds.TYPE_INSPECTOR_FLEET,
                    home);
            if (fleet == null) return null;
            fleet.setName("Office of the Inspector-General");
            fleet.setNoFactionInName(true);
            FleetMemberAPI flag = fleet.getFleetData().addFleetMember(TLCIds.VARIANT_PLENIPOTENTIARY);
            fleet.getFleetData().addFleetMember(TLCIds.VARIANT_MAGISTRATE);
            fleet.getFleetData().addFleetMember(TLCIds.VARIANT_MAGISTRATE);
            fleet.getFleetData().addFleetMember(TLCIds.VARIANT_ASSESSOR);
            fleet.getFleetData().addFleetMember(TLCIds.VARIANT_ASSESSOR_SUPPORT);
            fleet.getFleetData().addFleetMember(TLCIds.VARIANT_TALLY_WRIT);
            fleet.getFleetData().addFleetMember(TLCIds.VARIANT_TALLY_WRIT);
            if (flag == null) return null;

            PersonAPI ig = getOrCreateInspector();
            fleet.getFleetData().setFlagship(flag);
            flag.setCaptain(ig);
            fleet.setCommander(ig);
            flag.setShipName("DBV Final Reading");

            // The Plenipotentiary is always recoverable: the one prize the hearing can award.
            ShipVariantAPI v = flag.getVariant().clone();
            v.setSource(VariantSource.REFIT);
            v.addTag(Tags.VARIANT_ALWAYS_RECOVERABLE);
            flag.setVariant(v, false, true);

            for (FleetMemberAPI m : fleet.getFleetData().getMembersListCopy()) {
                m.getRepairTracker().setCR(m.getRepairTracker().getMaxCR());
            }
            fleet.getFleetData().sort();
            fleet.getFleetData().setSyncNeeded();
            fleet.getFleetData().syncIfNeeded();

            MemoryAPI mem = fleet.getMemoryWithoutUpdate();
            mem.set(TLCIds.MEM_IG_FLEET, true);
            mem.set(MemFlags.FLEET_FIGHT_TO_THE_LAST, true);
            // The hearing is between the player and the IG: no stations or bystander fleets join either side.
            mem.set(MemFlags.FLEET_INTERACTION_DIALOG_CONFIG_OVERRIDE_GEN, new TLCHearingConfigGen());
            Misc.makeImportant(fleet, REASON);
            fleet.setNoAutoDespawn(true);
            fleet.addEventListener(new TLCFleetListener(TLCFleetListener.KIND_IG));
            return fleet;
        } catch (Throwable t) {
            log.error("TLC: could not create the Inspector-General's fleet", t);
            return null;
        }
    }

    // ------------------------------------------------------------------------------------ fleet events
    static void onBattle(CampaignFleetAPI fleet, CampaignFleetAPI primaryWinner, BattleAPI battle) {
        if (fleet == null || battle == null) return;
        if (TLCIds.IG_RULED.equals(TLCMem.igState())) return;
        if (!battle.isPlayerInvolved() || !battle.isInvolved(fleet) || battle.onPlayerSide(fleet)) return;
        PersonAPI ig = Global.getSector().getImportantPeople().getPerson(TLCIds.ID_INSPECTOR);
        FleetMemberAPI flag = fleet.getFlagship();
        boolean flagshipLost = flag == null || flag.getCaptain() != ig
                || !TLCIds.HULL_PLENIPOTENTIARY.equals(flag.getHullId());
        if (!flagshipLost) {
            // The hearing went against the player (or was inconclusive): adjourn and wait at the Tallyhouse.
            sendHomeToWait(fleet);
            return;
        }
        TLCMem.setString(TLCIds.MEM_IG_STATE, TLCIds.IG_RULED);
        MemoryAPI mem = fleet.getMemoryWithoutUpdate();
        Misc.setFlagWithReason(mem, MemFlags.MEMORY_KEY_MAKE_HOSTILE, REASON, false, 0f);
        Misc.setFlagWithReason(mem, MemFlags.MEMORY_KEY_MAKE_AGGRESSIVE, REASON, false, 0f);
        setPursuit(fleet, false);
        Misc.makeUnimportant(fleet, REASON);
        fleet.clearAssignments();
        SectorEntityToken home = TLCMem.tallyhouse();
        if (home != null) {
            fleet.addAssignment(FleetAssignment.GO_TO_LOCATION_AND_DESPAWN, home, 200f, "returning with the finding");
        } else {
            fleet.despawn();
        }
        TLCHearingIntel intel = TLCHearingIntel.get();
        if (intel != null) intel.sendUpdateIfPlayerHasIntel(null, false);
        log.info("TLC: Inspector-General ruled - Domain contact presumed lost");
    }

    static void onFleetDespawned(CampaignFleetAPI fleet, FleetDespawnReason reason) {
        String s = TLCMem.igState();
        if (TLCIds.IG_RULED.equals(s)) return;
        // Lost for any other reason: the referral stands and a new hearing will be convened.
        if (TLCIds.IG_DISPATCHED.equals(s) || TLCIds.IG_WAITING.equals(s)) {
            TLCMem.setString(TLCIds.MEM_IG_STATE, TLCIds.IG_REFERRED);
        }
    }
}
