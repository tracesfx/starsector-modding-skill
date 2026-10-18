package {{PACKAGE}};

import com.fs.starfarer.api.Global;
import com.fs.starfarer.api.campaign.SectorEntityToken;
import com.fs.starfarer.api.campaign.comm.IntelInfoPlugin;
import com.fs.starfarer.api.impl.campaign.ids.Tags;
import com.fs.starfarer.api.impl.campaign.intel.BaseIntelPlugin;
import com.fs.starfarer.api.ui.SectorMapAPI;
import com.fs.starfarer.api.ui.TooltipMakerAPI;
import com.fs.starfarer.api.util.Misc;

import java.awt.Color;
import java.util.Set;

/**
 * Intel entry "{{NAME}}". Create once and add with Global.getSector().getIntelManager().addIntel(intel) (it is then
 * saved with the game: keep fields serializable and avoid references to UI or combat objects).
 * The icon is a settings.json graphics entry: "graphics": {"intel": {"{{PREFIX}}intel": "graphics/icons/intel/...png"}}
 * (vanilla intel icons are 40x40).
 */
public class {{CLASS}} extends BaseIntelPlugin {
    private final SectorEntityToken target;
    private int stage = 0;

    public {{CLASS}}(SectorEntityToken target) {
        this.target = target;
    }

    public static {{CLASS}} get() {
        IntelInfoPlugin p = Global.getSector().getIntelManager().getFirstIntel({{CLASS}}.class);
        return p instanceof {{CLASS}} ? ({{CLASS}}) p : null;
    }

    public void advanceStage() {
        stage++;
        sendUpdateIfPlayerHasIntel(null, false);
    }

    @Override
    protected String getName() {
        return "{{NAME}}";
    }

    @Override
    public String getIcon() {
        return Global.getSettings().getSpriteName("intel", "{{PREFIX}}intel");
    }

    @Override
    public Set<String> getIntelTags(SectorMapAPI map) {
        Set<String> tags = super.getIntelTags(map);
        tags.add(Tags.INTEL_STORY);
        return tags;
    }

    @Override
    protected void addBulletPoints(TooltipMakerAPI info, ListInfoMode mode, boolean isUpdate, Color tc, float initPad) {
        Color h = Misc.getHighlightColor();
        bullet(info);
        if (target != null) {
            info.addPara("Go to %s", initPad, tc, h, target.getName());
        }
        unindent(info);
    }

    @Override
    public void createSmallDescription(TooltipMakerAPI info, float width, float height) {
        float opad = 10f;
        info.addPara("Describe what the player knows and what to do next. Stage: %s.", opad,
                Misc.getHighlightColor(), "" + stage);
        addBulletPoints(info, ListInfoMode.IN_DESC);
    }

    @Override
    public SectorEntityToken getMapLocation(SectorMapAPI map) {
        return target;
    }
}
