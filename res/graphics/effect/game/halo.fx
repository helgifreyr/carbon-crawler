#include "common.fxh"

float4 HaloColor < bool SasUiVisible = true; > = float4(1.0, 0.8, 0.4, 1.0);
// x > 0: the halo belongs to something facing the model's +Z (a wall torch) and fades out when seen from behind it.
float4 HaloFacing < bool SasUiVisible = true; > = float4(0.0, 0.0, 0.0, 0.0);

texture2D DiffuseMap;
sampler DiffuseSampler = sampler_state
{
    Texture = <DiffuseMap>;
    MinFilter = Linear;
    MagFilter = Linear;
    MipFilter = None;
    AddressU = Clamp;
    AddressV = Clamp;
};

// Every corner of a halo quad sits at the halo centre; normal.x is its size and uv picks the corner.
struct VSIn
{
    float3 pos : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
};

struct VSOut
{
    float4 pos : SV_Position;
    float2 uv : TEXCOORD0;
    float fade : TEXCOORD1;
};

VSOut HaloVS(VSIn i)
{
    VSOut o;
    float4 world = mul(float4(i.pos, 1.0), WorldMat);
    float4 view = mul(world, ViewMat);
    float3 eye = float3(ViewInverseTransposeMat._m03, ViewInverseTransposeMat._m13, ViewInverseTransposeMat._m23);
    float3 facing = mul(float4(0.0, 0.0, 1.0, 0.0), WorldMat).xyz;
    float toward = dot(normalize(facing.xz + 1e-5), normalize(eye.xz - world.xz + 1e-5));
    o.fade = lerp(1.0, saturate(toward * 2.5 + 0.6), saturate(HaloFacing.x));
    view.xy += (i.uv * 2.0 - 1.0) * float2(1.0, -1.0) * i.normal.x;
    o.pos = mul(view, ProjectionMat);
    o.uv = i.uv;
    return o;
}

float4 HaloPS(VSOut i) : SV_Target
{
    float a = tex2D(DiffuseSampler, i.uv).a;
    return float4(HaloColor.rgb * a * HaloColor.a * i.fade, 1.0);
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
        VertexShader = compile vs_3_0 HaloVS();
        PixelShader = compile ps_3_0 HaloPS();
    }
}
