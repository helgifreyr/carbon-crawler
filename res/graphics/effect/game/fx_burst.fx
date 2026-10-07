#include "common.fxh"
#include "fx.fxh"

// x: speed, y: drag, z: gravity, w: upward bias of the spray
float4 FxMotion < bool SasUiVisible = true; > = float4(5.0, 3.0, -9.0, 0.3);
// Scales the random spray direction per axis: (1, 0.05, 1) makes a flat ring.
float4 FxShape < bool SasUiVisible = true; > = float4(1.0, 1.0, 1.0, 0.0);
// Added to the spray direction in model space: (0, 0.1, 1.5) turns a burst into a forward cone.
float4 FxBias < bool SasUiVisible = true; > = float4(0.0, 0.0, 0.0, 0.0);
// x: shortest particle life and y: slowest particle, as fractions; near 1 makes a burst end at a crisp radius.
float4 FxVary < bool SasUiVisible = true; > = float4(0.45, 0.35, 0.0, 0.0);

FxVSOut BurstVS(FxVSIn i)
{
    float3 dir = normalize((i.seed * 2.0 - 1.0) * FxShape.xyz + float3(0.0, FxMotion.w, 0.0) + FxBias.xyz);
    float life = FxTime.y * lerp(FxVary.x, 1.0, i.seed2.x);
    float u = saturate(FxTime.x / life);
    float t = min(FxTime.x, life);
    float speed = FxMotion.x * lerp(FxVary.y, 1.0, i.seed2.y);
    float drag = max(FxMotion.y, 0.001);
    float3 p = dir * speed * (1.0 - exp(-drag * t)) / drag + float3(0.0, 0.5 * FxMotion.z * t * t, 0.0);
    float size = lerp(FxSize.x, FxSize.y, u) * lerp(0.6, 1.3, i.seed2.y) * step(FxTime.x, life);
    return FxBillboard(p, i.corner, size, u);
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
        VertexShader = compile vs_3_0 BurstVS();
        PixelShader = compile ps_3_0 FxPS();
    }
}
