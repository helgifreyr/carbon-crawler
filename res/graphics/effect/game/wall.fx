#include "common.fxh"
#include "lit.fxh"

// SeeThrough: focus point (the player) and hole radius; EyePos: the camera. Wall pixels between the two are dithered
// away, so the player is never hidden behind a wall.
float4 SeeThrough < bool SasUiVisible = true; > = float4(0.0, -1000.0, 0.0, 0.0);
float4 EyePos < bool SasUiVisible = true; > = float4(0.0, 0.0, 0.0, 1.0);

struct VSIn
{
    float3 pos : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
};

LitVSOut WallVS(VSIn i)
{
    return LitVertex(i.pos, i.normal, i.uv);
}

float4 WallPS(LitVSOut i) : SV_Target
{
    float3 toFocus = SeeThrough.xyz - EyePos.xyz;
    float len = length(toFocus);
    float3 dir = toFocus / max(len, 0.001);
    float t = dot(i.world - EyePos.xyz, dir);
    float d = length(i.world - (EyePos.xyz + dir * t));
    float between = step(t, len - 0.4);
    float hole = saturate(1.4 - d / max(SeeThrough.w, 0.001)) * between;
    float noise = frac(sin(dot(floor(i.world * 24.0), float3(12.9898, 78.233, 37.719))) * 43758.5453);
    clip(noise - hole * 0.92);
    return float4(LitColor(i), 1.0);
}

technique Main
{
    pass P0
    {
        ZEnable = true;
        ZWriteEnable = true;
        CullMode = None;
        AlphaBlendEnable = false;
        VertexShader = compile vs_3_0 WallVS();
        PixelShader = compile ps_3_0 WallPS();
    }
}
