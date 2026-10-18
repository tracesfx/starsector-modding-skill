package tlc.compat;

import org.dark.shaders.light.LightData;

/**
 * Optional GraphicsLib integration. Only referenced from TLCModPlugin after checking that GraphicsLib
 * ("shaderLib") is enabled, so this class (and its GraphicsLib import) is never loaded without it.
 */
public final class TLCGraphicsLibCompat {
    public static final String LIGHT_DATA = "data/lights/tlc_light_data.csv";

    private TLCGraphicsLibCompat() {
    }

    public static void loadLights() {
        LightData.readLightDataCSV(LIGHT_DATA);
    }
}
