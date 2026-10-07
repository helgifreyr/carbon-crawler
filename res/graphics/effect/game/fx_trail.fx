#include "common.fxh"
#include "fx.fxh"

// x: length behind the bolt, y: sideways spread, z: cycles per second, w: flight speed (caps length early on)
float4 FxTrail < bool SasUiVisible = true; > = float4(1.6, 0.16, 5.0, 30.0);

FxVSOut TrailVS(FxVSIn i)
{
    float phase = frac(FxTime.x * FxTrail.z + i.seed2.x);
    float length = min(FxTrail.x, FxTime.x * FxTrail.w);
    float2 jitter = (i.seed.xy * 2.0 - 1.0) * FxTrail.y * phase;
    float3 p = float3(jitter.x, jitter.y + 0.15 * phase, -phase * length);
    float size = lerp(FxSize.x, FxSize.y, phase) * lerp(0.7, 1.2, i.seed.z);
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
        VertexShader = compile vs_3_0 TrailVS();
        PixelShader = compile ps_3_0 FxPS();
    }
}
