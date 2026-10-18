package tlc;

/**
 * Every id the mod's Java refers to. tools/validate.py resolves each prefixed constant against the
 * data files (HULL_ -> ship_data.csv, WEAPON_ -> weapon_data.csv, ...), so a typo here fails the build.
 */
public final class TLCIds {
    private TLCIds() {
    }

    public static final String MOD_ID = "the_last_census";

    // ---- registries (validated)
    public static final String FACTION_BUREAU = "tlc_bureau";

    public static final String HULL_TALLY = "tlc_tally";
    public static final String HULL_ASSESSOR = "tlc_assessor";
    public static final String HULL_MAGISTRATE = "tlc_magistrate";
    public static final String HULL_EXCHEQUER = "tlc_exchequer";
    public static final String HULL_PLENIPOTENTIARY = "tlc_plenipotentiary";

    public static final String VARIANT_TALLY = "tlc_tally_Standard";
    public static final String VARIANT_TALLY_WRIT = "tlc_tally_Writ";
    public static final String VARIANT_ASSESSOR = "tlc_assessor_Standard";
    public static final String VARIANT_ASSESSOR_SUPPORT = "tlc_assessor_Support";
    public static final String VARIANT_MAGISTRATE = "tlc_magistrate_Standard";
    public static final String VARIANT_EXCHEQUER = "tlc_exchequer_Standard";
    public static final String VARIANT_PLENIPOTENTIARY = "tlc_plenipotentiary_Standard";

    public static final String WEAPON_WRIT = "tlc_writ";
    public static final String WEAPON_SUBPOENA = "tlc_subpoena";
    public static final String WEAPON_ACCRUAL = "tlc_accrual";
    public static final String WEAPON_INJUNCTION = "tlc_injunction";
    public static final String WEAPON_FORECLOSURE = "tlc_foreclosure";

    public static final String HULLMOD_PROTOCOLS = "tlc_protocols";
    public static final String SYSTEM_SURCHARGE = "tlc_surcharge";
    public static final String SYSTEM_JUDGMENT = "tlc_summary_judgment";
    public static final String CONDITION_AUTOMATED_ADMIN = "tlc_automated_admin";
    public static final String ITEM_BUREAU_PACKAGE = "tlc_bureau_package";

    public static final String ENTITY_TALLYHOUSE = "tlc_tallyhouse";
    public static final String ENTITY_COURIER_RELAY = "tlc_courier_relay";
    public static final String ENTITY_DEAD_LETTER_OFFICE = "tlc_dead_letter_office";

    public static final String DESC_TALLYHOUSE = "tlc_tallyhouse";
    public static final String DESC_DOCKET = "tlc_planet_docket";
    public static final String DESC_ABEYANCE = "tlc_planet_abeyance";
    public static final String DESC_ESCROW = "tlc_planet_escrow";
    public static final String DESC_ENVOI = "tlc_planet_envoi";

    public static final String PORTRAIT_REGISTRAR = "graphics/portraits/tlc_registrar.png";
    public static final String PORTRAIT_INSPECTOR = "graphics/portraits/tlc_inspector_general.png";
    public static final String PORTRAIT_ASSESSOR = "graphics/portraits/tlc_assessor.png";

    public static final String LUNA_ENABLE_AUDITS = "tlc_enableAudits";
    public static final String LUNA_MAX_ASSESSORS = "tlc_maxAssessorFleets";

    public static final String INDUSTRY_POPULATION = "population";
    public static final String INDUSTRY_SPACEPORT = "spaceport";
    public static final String INDUSTRY_MILITARY_BASE = "militarybase";
    public static final String INDUSTRY_BATTLESTATION = "battlestation_high";
    public static final String INDUSTRY_BATTERIES = "heavybatteries";
    public static final String INDUSTRY_HEAVY = "heavyindustry";

    public static final String SUBMARKET_OPEN = "open_market";
    public static final String SUBMARKET_MILITARY = "generic_military";
    public static final String SUBMARKET_STORAGE = "storage";

    public static final String COMMODITY_DRUGS = "drugs";
    public static final String COMMODITY_ORGANS = "organs";
    public static final String COMMODITY_ALPHA = "alpha_core";
    public static final String COMMODITY_BETA = "beta_core";
    public static final String COMMODITY_GAMMA = "gamma_core";

    // ---- instance ids (entities, markets, people, fleet types) - not registry ids
    public static final String ID_SYSTEM_ASSIZE = "Assize";
    public static final String ID_SYSTEM_ENVOI = "Envoi";
    public static final String ID_TALLYHOUSE_ENTITY = "tlc_tallyhouse_station";
    public static final String ID_TALLYHOUSE_MARKET = "tlc_tallyhouse_market";
    public static final String ID_RELAY_ENTITY = "tlc_envoi_relay";
    public static final String ID_DLO_ENTITY = "tlc_dead_letter_annex";
    public static final String ID_DOCKET = "tlc_docket";
    public static final String ID_REGISTRAR = "tlc_registrar";
    public static final String ID_INSPECTOR = "tlc_inspector_general";
    public static final String TYPE_ASSESSOR_FLEET = "tlc_assessor";
    public static final String TYPE_INSPECTOR_FLEET = "tlc_inspector";
    public static final String HASSLE_AUDIT = "tlc_audit";
    public static final String SEIZED_TAG = "tlc_seized";
    public static final String REASON_STORY = "tlc_census";

    // ---- memory keys
    public static final String MEM_GENERATED = "$tlc_generated";
    public static final String MEM_STAGE = "$tlc_stage";
    public static final String MEM_ENDING = "$tlc_ending";
    public static final String MEM_RETURNS = "$tlc_returnsFiled";
    public static final String MEM_ENUMERATOR = "$tlc_enumerator";
    public static final String MEM_COMMISSIONER = "$tlc_commissioner";
    public static final String MEM_AUDITS_ENDED = "$tlc_auditsEnded";
    public static final String MEM_CERTIFIED = "$tlc_certified";
    public static final String MEM_AUDIT_COUNT = "$tlc_auditCount";
    public static final String MEM_NO_DOMAIN_COUNT = "$tlc_noDomainCount";
    public static final String MEM_IG_STATE = "$tlc_igState";
    public static final String MEM_HAS_LETTER = "$tlc_hasLetter";
    public static final String MEM_LETTER_DELIVERED = "$tlc_letterDelivered";
    public static final String MEM_DLO_SEARCHED = "$tlc_dloSearched";
    public static final String MEM_LETTERS_READ = "$tlc_lettersRead";
    public static final String MEM_RELAY_ACTIVE = "$tlc_relayActive";
    public static final String MEM_ASKED_AUDIT = "$tlc_askedAudit";
    public static final String MEM_CENSUS_FILED = "$tlc_censusFiled";
    public static final String MEM_TALLYHOUSE = "$tlc_tallyhouse";
    public static final String MEM_ASSESSOR_FLEET = "$tlc_assessor";
    public static final String MEM_IG_FLEET = "$tlc_igFleet";
    public static final String MEM_RELAY_PIRATES = "$tlc_relayPirates";
    public static final String MEM_AUDIT_CONV = "$tlc_auditConv";
    public static final String MEM_IG_CONV = "$tlc_igConv";

    // ---- quest stages (values of MEM_STAGE)
    public static final String STAGE_BROADCAST = "broadcast";
    public static final String STAGE_REPORT = "report";
    public static final String STAGE_RETURNS = "returns";
    public static final String STAGE_RELAY = "relay";
    public static final String STAGE_DONE = "done";

    public static final String ENDING_ARCHIVED = "archived";
    public static final String ENDING_CONTINUING = "continuing";

    // ---- Inspector-General states (values of MEM_IG_STATE)
    public static final String IG_NONE = "none";
    public static final String IG_REFERRED = "referred";
    public static final String IG_DISPATCHED = "dispatched";
    public static final String IG_WAITING = "waiting";
    public static final String IG_RULED = "ruled";

    public static final int RETURNS_REQUIRED = 3;
    public static final int NO_DOMAIN_THRESHOLD = 3;
}
