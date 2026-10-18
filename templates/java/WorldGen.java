package {{PACKAGE}};

import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.campaign.PlanetAPI;
import com.fs.starfarer.api.campaign.SectorAPI;
import com.fs.starfarer.api.campaign.SectorEntityToken;
import com.fs.starfarer.api.campaign.StarSystemAPI;
import com.fs.starfarer.api.campaign.econ.MarketAPI;
import com.fs.starfarer.api.impl.campaign.ids.Conditions;
import com.fs.starfarer.api.impl.campaign.ids.Entities;
import com.fs.starfarer.api.impl.campaign.ids.Factions;
import com.fs.starfarer.api.impl.campaign.ids.Industries;
import com.fs.starfarer.api.impl.campaign.ids.StarTypes;
import com.fs.starfarer.api.impl.campaign.ids.Submarkets;
import com.fs.starfarer.api.impl.campaign.ids.Terrain;
import com.fs.starfarer.api.impl.campaign.intel.deciv.DecivTracker;
import com.fs.starfarer.api.impl.campaign.procgen.NebulaEditor;
import com.fs.starfarer.api.impl.campaign.terrain.HyperspaceTerrainPlugin;
import com.fs.starfarer.api.util.Misc;
import org.apache.log4j.Logger;
import org.lwjgl.util.vector.Vector2f;

import java.awt.Color;

/**
 * World generation "{{NAME}}": one star system with a planet, a station and a populated station market.
 * Proven recipe (from a finished mod, checked against vanilla): idempotent (safe from onNewGame AND onGameLoad),
 * finds free hyperspace, clears hyperspace storms around the system, sets the market's survey level, and protects a
 * quest-critical market from saturation bombardment and decivilization until the quest releases it.
 *
 * Call {{CLASS}}.generate(Global.getSector()) from the ModPlugin's generateIfNeeded.
 */
public final class {{CLASS}} {
    private static final Logger log = Global.getLogger({{CLASS}}.class);
    public static final String STAR_SYSTEM_ID = "{{PREFIX}}system";           // star system id (also its name key)
    public static final String STATION_ID = "{{PREFIX}}station";         // entity instance id
    public static final String MARKET_ID = "{{PREFIX}}station_market";   // market id (Global.getSector().getEconomy().getMarket)
    public static final String STORY_REASON = "{{PREFIX}}story";
    private static final Vector2f PREFERRED_LOCATION = new Vector2f(-4000f, 9000f);
    private static final float MIN_SYSTEM_SEPARATION = 2600f;

    private {{CLASS}}() {
    }

    public static void generate(SectorAPI sector) {
        if (sector == null || sector.getStarSystem(STAR_SYSTEM_ID) != null) return;
        String faction = Factions.INDEPENDENT; // use your own faction id once its .faction file loads
        StarSystemAPI system = sector.createStarSystem(STAR_SYSTEM_ID);
        Vector2f loc = findFreeHyperspaceLocation(sector, PREFERRED_LOCATION);
        system.getLocation().set(loc.x, loc.y);
        system.setBackgroundTextureFilename("graphics/backgrounds/background4.jpg");

        PlanetAPI star = system.initStar(STAR_SYSTEM_ID + "_star", StarTypes.ORANGE, 500f, 300f);
        system.setLightColor(new Color(255, 230, 205));

        PlanetAPI planet = system.addPlanet(STAR_SYSTEM_ID + "_planet", star, "{{NAME}} I", "barren", 30f, 120f, 2600f, 80f);
        // planet.setCustomDescriptionId("{{PREFIX}}planet"); // needs a (id, CUSTOM) row in descriptions.csv

        SectorEntityToken station = system.addCustomEntity(STATION_ID, "{{NAME}} Station",
                Entities.STATION_BUILT_FROM_INDUSTRY, faction);
        station.setCircularOrbitPointingDown(planet, 45f, 300f, 30f);

        SectorEntityToken relay = system.addCustomEntity(STAR_SYSTEM_ID + "_relay", null, Entities.COMM_RELAY, faction);
        relay.setCircularOrbitPointingDown(star, 140f, 4200f, 160f);

        system.addAsteroidBelt(star, 80, 5600f, 300f, 200f, 300f, Terrain.ASTEROID_BELT, null);
        system.autogenerateHyperspaceJumpPoints(true, true);
        clearHyperspaceAround(system);
        createMarket(station, faction);
        log.info("{{CLASS}}: generated " + system.getName() + " at " + loc);
    }

    private static void createMarket(SectorEntityToken station, String faction) {
        MarketAPI market = Global.getFactory().createMarket(MARKET_ID, station.getName(), 4);
        market.setFactionId(faction);
        market.setPrimaryEntity(station);
        market.getTariff().modifyFlat("default_tariff", market.getFaction().getTariffFraction()); // as vanilla (Galatia.java)
        market.addCondition(Conditions.POPULATION_4);
        market.addIndustry(Industries.POPULATION);
        market.addIndustry(Industries.SPACEPORT);
        market.addIndustry(Industries.BATTLESTATION);
        market.addSubmarket(Submarkets.SUBMARKET_OPEN);
        market.addSubmarket(Submarkets.GENERIC_MILITARY);
        market.addSubmarket(Submarkets.SUBMARKET_STORAGE);
        market.setSurveyLevel(MarketAPI.SurveyLevel.FULL); // easy to forget: unsurveyed markets show "?" everywhere
        station.setMarket(market);
        station.setFaction(faction);
        Global.getSector().getEconomy().addMarket(market, true);
    }

    /** Quest-critical market: immune to saturation bombardment and decivilization until released. */
    public static void protect(MarketAPI market) {
        if (market == null) return;
        Misc.makeStoryCritical(market, STORY_REASON);
        market.getMemoryWithoutUpdate().set(DecivTracker.NO_DECIV_KEY, true);
    }

    /** Every protection you add needs a documented removal point: call this when the quest is over. */
    public static void release(MarketAPI market) {
        if (market == null) return;
        Misc.makeNonStoryCritical(market, STORY_REASON);
        market.getMemoryWithoutUpdate().unset(DecivTracker.NO_DECIV_KEY);
    }

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
        return new Vector2f(preferred);
    }

    private static boolean isFree(SectorAPI sector, Vector2f c) {
        for (StarSystemAPI s : sector.getStarSystems()) {
            if (s != null && s.getLocation() != null && Misc.getDistance(s.getLocation(), c) < MIN_SYSTEM_SEPARATION) {
                return false;
            }
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
            log.warn("{{CLASS}}: could not clear hyperspace around " + system.getName(), t);
        }
    }
}
