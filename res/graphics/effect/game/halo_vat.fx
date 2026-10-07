#include "common.fxh"
#include "vat.fxh"

float4 HaloColor < bool SasUiVisible = true; > = float4(1.0, 0.8, 0.4, 1.0);

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

// Like halo.fx, but the halo centre follows its bone through the vertex animation texture.
struct VSIn
{
    float3 pos : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
    float2 vat : TEXCOORD1;
};

struct VSOut
{
    float4 pos : SV_Position;
    float2 uv : TEXCOORD0;
};

VSOut HaloVS(VSIn i)
{
    VSOut o;
    float4 view = mul(mul(float4(VatLookup(VatPosSampler, i.vat.x), 1.0), WorldMat), ViewMat);
    view.xy += (i.uv * 2.0 - 1.0) * float2(1.0, -1.0) * i.normal.x;
    o.pos = mul(view, ProjectionMat);
    o.uv = i.uv;
    return o;
}

float4 HaloPS(VSOut i) : SV_Target
{
    float a = tex2D(DiffuseSampler, i.uv).a;
    return float4(HaloColor.rgb * a * HaloColor.a, 1.0);
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
