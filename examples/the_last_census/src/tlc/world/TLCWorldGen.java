package tlc.world;

import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.campaign.FactionAPI;
import com.fs.starfarer.api.campaign.PlanetAPI;
import com.fs.starfarer.api.campaign.SectorAPI;
import com.fs.starfarer.api.campaign.SectorEntityToken;
import com.fs.starfarer.api.campaign.StarSystemAPI;
import com.fs.starfarer.api.campaign.econ.MarketAPI;
import com.fs.starfarer.api.characters.FullName;
import com.fs.starfarer.api.characters.ImportantPeopleAPI;
import com.fs.starfarer.api.characters.PersonAPI;
import com.fs.starfarer.api.impl.campaign.ids.Factions;
import com.fs.starfarer.api.impl.campaign.ids.Ranks;
import com.fs.starfarer.api.impl.campaign.ids.StarTypes;
import com.fs.starfarer.api.impl.campaign.ids.Terrain;
import com.fs.starfarer.api.impl.campaign.intel.deciv.DecivTracker;
import com.fs.starfarer.api.impl.campaign.procgen.NebulaEditor;
import com.fs.starfarer.api.impl.campaign.terrain.HyperspaceTerrainPlugin;
import com.fs.starfarer.api.util.Misc;
import org.apache.log4j.Logger;
import org.lwjgl.util.vector.Vector2f;
import tlc.TLCIds;

import java.awt.Color;

/**
 * Generates the Assize and Envoi systems, the Tallyhouse market and the Bureau's people.
 * Every entry point is idempotent so it is safe to call from onNewGame AND onGameLoad.
 */
public final class TLCWorldGen {
    private static final Logger log = Global.getLogger(TLCWorldGen.class);

    /** Preferred hyperspace location of Assize: open space north of Zagan, ~3.5 LY from the core's edge. */
    private static final Vector2f ASSIZE_PREFERRED = new Vector2f(-1800f, 9800f);
    private static final Vector2f ENVOI_OFFSET = new Vector2f(5200f, 3600f);
    private static final float MIN_SYSTEM_SEPARATION = 2600f;

    private TLCWorldGen() {
    }

    public static void generateIfNeeded(SectorAPI sector) {
        if (sector == null) return;
        if (sector.getMemoryWithoutUpdate().getBoolean(TLCIds.MEM_GENERATED)) return;
        if (sector.getFaction(TLCIds.FACTION_BUREAU) == null) {
            log.error("TLC: faction " + TLCIds.FACTION_BUREAU + " is not loaded; skipping world generation");
            return;
        }
        StarSystemAPI assize = sector.getStarSystem(TLCIds.ID_SYSTEM_ASSIZE);
        if (assize == null) assize = generateAssize(sector);
        if (sector.getStarSystem(TLCIds.ID_SYSTEM_ENVOI) == null) generateEnvoi(sector, assize);
        setupRelations(sector);
        ensurePeople(sector);
        sector.getMemoryWithoutUpdate().set(TLCIds.MEM_GENERATED, true);
        log.info("TLC: Assize and Envoi generated");
    }

    // ------------------------------------------------------------------------------------------ Assize
    private static StarSystemAPI generateAssize(SectorAPI sector) {
        Vector2f loc = findFreeHyperspaceLocation(sector, ASSIZE_PREFERRED);
        StarSystemAPI system = sector.createStarSystem(TLCIds.ID_SYSTEM_ASSIZE);
        system.getLocation().set(loc.x, loc.y);
        system.setBackgroundTextureFilename("graphics/backgrounds/background2.jpg");

        PlanetAPI star = system.initStar("tlc_assize_star", StarTypes.ORANGE, 520f, 340f);
        system.setLightColor(new Color(255, 232, 206));

        PlanetAPI docket = system.addPlanet(TLCIds.ID_DOCKET, star, "Docket", "barren_castiron", 40f, 110f, 2400f, 64f);
        docket.setCustomDescriptionId(TLCIds.DESC_DOCKET);

        PlanetAPI abeyance = system.addPlanet("tlc_abeyance", star, "Abeyance", "gas_giant", 200f, 310f, 5600f, 240f);
        abeyance.setCustomDescriptionId(TLCIds.DESC_ABEYANCE);

        SectorEntityToken station = system.addCustomEntity(TLCIds.ID_TALLYHOUSE_ENTITY, "The Tallyhouse",
                TLCIds.ENTITY_TALLYHOUSE, TLCIds.FACTION_BUREAU);
        station.setCircularOrbitPointingDown(abeyance, 45f, 640f, 36f);
        station.setCustomDescriptionId(TLCIds.DESC_TALLYHOUSE);

        SectorEntityToken relay = system.addCustomEntity("tlc_assize_relay", "Assize Relay", "comm_relay",
                TLCIds.FACTION_BUREAU);
        relay.setCircularOrbitPointingDown(star, 140f, 4000f, 150f);
        SectorEntityToken buoy = system.addCustomEntity("tlc_assize_buoy", "Assize Buoy", "nav_buoy",
                TLCIds.FACTION_BUREAU);
        buoy.setCircularOrbitPointingDown(star, 260f, 4000f, 150f);

        system.addRingBand(star, "misc", "rings_asteroids0", 256f, 1, new Color(200, 188, 168, 255), 256f, 7600f,
                300f, Terrain.RING, null);
        system.addAsteroidBelt(star, 110, 7600f, 320f, 240f, 360f, Terrain.ASTEROID_BELT, "The Margins");

        PlanetAPI escrow = system.addPlanet("tlc_escrow", star, "Escrow", "frozen", 300f, 150f, 10200f, 520f);
        escrow.setCustomDescriptionId(TLCIds.DESC_ESCROW);

        // The Dead Letter Office: a small derelict far out in the dark. Must be found with sensors.
        SectorEntityToken dlo = system.addCustomEntity(TLCIds.ID_DLO_ENTITY, null, TLCIds.ENTITY_DEAD_LETTER_OFFICE,
                Factions.NEUTRAL);
        dlo.setCircularOrbitWithSpin(star, 333f, 14500f, 1100f, 2f, 5f);
        dlo.setSensorProfile(1f);
        dlo.setDiscoverable(true);
        dlo.getDetectedRangeMod().modifyFlat("tlc_gen", 1500f);
        dlo.setDiscoveryXP(2500f);

        system.autogenerateHyperspaceJumpPoints(true, true);
        clearHyperspaceAround(system);
        createTallyhouseMarket(station);
        return system;
    }

    private static void createTallyhouseMarket(SectorEntityToken station) {
        MarketAPI market = Global.getFactory().createMarket(TLCIds.ID_TALLYHOUSE_MARKET, "The Tallyhouse", 4);
        market.setFactionId(TLCIds.FACTION_BUREAU);
        market.setPrimaryEntity(station);
        market.getTariff().modifyFlat("generator", 0.3f);
        market.addCondition("population_4");
        market.addCondition(TLCIds.CONDITION_AUTOMATED_ADMIN);
        market.addIndustry(TLCIds.INDUSTRY_POPULATION);
        market.addIndustry(TLCIds.INDUSTRY_SPACEPORT);
        market.addIndustry(TLCIds.INDUSTRY_HEAVY);
        market.addIndustry(TLCIds.INDUSTRY_MILITARY_BASE);
        market.addIndustry(TLCIds.INDUSTRY_BATTLESTATION);
        market.addIndustry(TLCIds.INDUSTRY_BATTERIES);
        market.addSubmarket(TLCIds.SUBMARKET_OPEN);
        market.addSubmarket(TLCIds.SUBMARKET_MILITARY);
        market.addSubmarket(TLCIds.SUBMARKET_STORAGE);
        market.getMemoryWithoutUpdate().set(TLCIds.MEM_TALLYHOUSE, true);
        market.setSurveyLevel(MarketAPI.SurveyLevel.FULL);
        protectTallyhouse(market);
        station.setMarket(market);
        station.setFaction(TLCIds.FACTION_BUREAU);
        Global.getSector().getEconomy().addMarket(market, true);
    }

    // ------------------------------------------------------------------------------------------ Envoi
    private static void generateEnvoi(SectorAPI sector, StarSystemAPI assize) {
        Vector2f base = assize != null ? assize.getLocation() : ASSIZE_PREFERRED;
        Vector2f loc = findFreeHyperspaceLocation(sector, new Vector2f(base.x + ENVOI_OFFSET.x, base.y + ENVOI_OFFSET.y));
        StarSystemAPI system = sector.createStarSystem(TLCIds.ID_SYSTEM_ENVOI);
        system.getLocation().set(loc.x, loc.y);
        system.setBackgroundTextureFilename("graphics/backgrounds/background5.jpg");

        PlanetAPI star = system.initStar("tlc_envoi_star", StarTypes.RED_DWARF, 380f, 220f);
        system.setLightColor(new Color(255, 196, 176));

        PlanetAPI rock = system.addPlanet("tlc_envoi_rock", star, "Envoi I", "irradiated", 120f, 120f, 2100f, 90f);
        rock.setCustomDescriptionId(TLCIds.DESC_ENVOI);

        SectorEntityToken relay = system.addCustomEntity(TLCIds.ID_RELAY_ENTITY, "Bureau Courier Relay",
                TLCIds.ENTITY_COURIER_RELAY, Factions.NEUTRAL);
        relay.setCircularOrbitPointingDown(star, 300f, 3300f, 160f);

        system.addAsteroidBelt(star, 60, 4600f, 400f, 200f, 300f, Terrain.ASTEROID_BELT, null);
        system.autogenerateHyperspaceJumpPoints(true, true);
        clearHyperspaceAround(system);
    }

    // ------------------------------------------------------------------------------------------ helpers
    private static Vector2f findFreeHyperspaceLocation(SectorAPI sector, Vector2f preferred) {
        for (int ring = 0; ring < 14; ring++) {
            float r = ring * 1400f;
            int steps = ring == 0 ? 1 : 8 + ring * 4;
            for (int i = 0; i < steps; i++) {
                double a = i * 2.0 * Math.PI / steps;
                Vector2f c = new Vector2f(preferred.x + (float) Math.cos(a) * r, preferred.y + (float) Math.sin(a) * r);
                if (isFree(sector, c)) return c;
            }
        }
        log.warn("TLC: no free hyperspace location near " + preferred + ", using preferred location");
        return new Vector2f(preferred);
    }

    private static boolean isFree(SectorAPI sector, Vector2f c) {
        for (StarSystemAPI s : sector.getStarSystems()) {
            if (s == null || s.getLocation() == null) continue;
            if (Misc.getDistance(s.getLocation(), c) < MIN_SYSTEM_SEPARATION) return false;
        }
        return true;
    }

    private static void clearHyperspaceAround(StarSystemAPI system) {
        try {
            if (Misc.getHyperspaceTerrain() == null) return;
            HyperspaceTerrainPlugin plugin = (HyperspaceTerrainPlugin) Misc.getHyperspaceTerrain().getPlugin();
            NebulaEditor editor = new NebulaEditor(plugin);
            float minRadius = plugin.getTileSize() * 2f;
            float radius = system.getMaxRadiusInHyperspace();
            editor.clearArc(system.getLocation().x, system.getLocation().y, 0, radius + minRadius * 0.5f, 0, 360f);
            editor.clearArc(system.getLocation().x, system.getLocation().y, 0, radius + minRadius, 0, 360f, 0.25f);
        } catch (Throwable t) {
            log.warn("TLC: could not clear hyperspace storms around " + system.getName(), t);
        }
    }

    private static void setupRelations(SectorAPI sector) {
        FactionAPI bureau = sector.getFaction(TLCIds.FACTION_BUREAU);
        if (bureau == null) return;
        setRel(sector, bureau, Factions.PIRATES, -0.6f);
        setRel(sector, bureau, Factions.LUDDIC_PATH, -0.6f);
        setRel(sector, bureau, Factions.HEGEMONY, -0.4f);
        setRel(sector, bureau, Factions.TRITACHYON, -0.15f);
        setRel(sector, bureau, Factions.DIKTAT, -0.1f);
        setRel(sector, bureau, Factions.REMNANTS, -1f);
        setRel(sector, bureau, Factions.DERELICT, -1f);
        setRel(sector, bureau, Factions.OMEGA, -1f);
        setRel(sector, bureau, Factions.THREAT, -1f);
        setRel(sector, bureau, Factions.DWELLER, -1f);
        setRel(sector, bureau, Factions.PLAYER, 0f);
    }

    private static void setRel(SectorAPI sector, FactionAPI bureau, String other, float rel) {
        if (other == null || sector.getFaction(other) == null) return;
        bureau.setRelationship(other, rel);
    }

    /**
     * The questline runs through the Tallyhouse, so until it is finished the market is story-critical (immune to
     * destruction by saturation bombardment) and exempt from decivilization. Released by TLCQuest on completion.
     */
    public static void protectTallyhouse(MarketAPI market) {
        if (market == null) return;
        Misc.makeStoryCritical(market, TLCIds.REASON_STORY);
        market.getMemoryWithoutUpdate().set(DecivTracker.NO_DECIV_KEY, true);
    }

    public static void releaseTallyhouse(MarketAPI market) {
        if (market == null) return;
        Misc.makeNonStoryCritical(market, TLCIds.REASON_STORY);
        market.getMemoryWithoutUpdate().unset(DecivTracker.NO_DECIV_KEY);
    }

    /** Creates the Registrar if missing and (re)attaches it to the Tallyhouse market. Idempotent. */
    public static void ensurePeople(SectorAPI sector) {
        if (sector == null) return;
        try {
            ImportantPeopleAPI ip = sector.getImportantPeople();
            PersonAPI reg = ip.getPerson(TLCIds.ID_REGISTRAR);
            if (reg == null) {
                reg = Global.getFactory().createPerson();
                reg.setId(TLCIds.ID_REGISTRAR);
                reg.setFaction(TLCIds.FACTION_BUREAU);
                reg.setName(new FullName("Registrar", "of Assize", FullName.Gender.ANY));
                reg.setPortraitSprite(TLCIds.PORTRAIT_REGISTRAR);
                reg.setRankId(Ranks.FACTION_LEADER);
                reg.setPostId(Ranks.POST_FACTION_LEADER);
                ip.addPerson(reg);
            }
            MarketAPI market = Global.getSector().getEconomy().getMarket(TLCIds.ID_TALLYHOUSE_MARKET);
            if (market != null && TLCIds.FACTION_BUREAU.equals(market.getFactionId())) {
                if (!TLCIds.STAGE_DONE.equals(sector.getMemoryWithoutUpdate().getString(TLCIds.MEM_STAGE))) {
                    protectTallyhouse(market);
                }
                if (market.getAdmin() != reg) market.setAdmin(reg);
                if (market.getCommDirectory() != null && market.getCommDirectory().getEntryForPerson(reg) == null) {
                    market.getCommDirectory().addPerson(reg);
                }
                if (!market.getPeopleCopy().contains(reg)) market.addPerson(reg);
            }
        } catch (Throwable t) {
            log.error("TLC: ensurePeople failed", t);
        }
    }
}
