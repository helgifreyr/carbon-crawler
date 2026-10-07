#include "common.fxh"
#include "fx.fxh"

// x: flame height, y: base radius, z: cycles per second
float4 FxFlame < bool SasUiVisible = true; > = float4(0.45, 0.07, 2.2, 0.0);

FxVSOut FlameVS(FxVSIn i)
{
    float phase = frac(FxTime.x * FxFlame.z * lerp(0.8, 1.2, i.seed.z) + i.seed2.x);
    float2 spread = (i.seed.xy * 2.0 - 1.0) * FxFlame.y * (1.0 - 0.6 * phase);
    float sway = sin(FxTime.x * 7.0 + i.seed2.y * 6.28) * 0.02 * phase;
    float3 p = float3(spread.x + sway, phase * FxFlame.x, spread.y);
    float size = lerp(FxSize.x, FxSize.y, phase) * lerp(0.7, 1.2, i.seed2.y);
    return FxBillboard(p, i.corner, size, phase);
}

technique Main
{
    pass P0
    {
        ZEnable = true;
        ZWriteEnable = false;
        CullMode = None;
        AlphaBlendEnable = true;
        SrcBlend = One;
        DestBlend = One;
        VertexShader = compile vs_3_0 FlameVS();
        PixelShader = compile ps_3_0 FxPS();
    }
}
