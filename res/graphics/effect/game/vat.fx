#include "common.fxh"
#include "lit.fxh"
#include "vat.fxh"

float4 Flash < bool SasUiVisible = true; > = float4(0.0, 0.0, 0.0, 0.0);
// rgb: tint colour, w: amount (frost-slowed enemies turn icy).
float4 Tint < bool SasUiVisible = true; > = float4(0.0, 0.0, 0.0, 0.0);

texture2D VatNrm;
sampler VatNrmSampler = sampler_state
{
    Texture = <VatNrm>;
    MinFilter = Point;
    MagFilter = Point;
    MipFilter = None;
    AddressU = Clamp;
    AddressV = Clamp;
};

struct VSIn
{
    float3 pos : POSITION;
    float3 normal : NORMAL;
    float2 uv : TEXCOORD0;
    float2 vat : TEXCOORD1;
};

LitVSOut VatVS(VSIn i)
{
    return LitVertex(VatLookup(VatPosSampler, i.vat.x), normalize(VatLookup(VatNrmSampler, i.vat.x)), i.uv);
}

float4 VatPS(LitVSOut i) : SV_Target
{
    float3 color = LitColor(i);
    float luma = dot(color, float3(0.3, 0.59, 0.11));
    color = lerp(color, Tint.rgb * (0.35 + luma * 1.4), Tint.w);
    return float4(lerp(color, float3(1.0, 0.86, 0.8), Flash.x), 1.0);
}

technique Main
{
    pass P0
    {
        ZEnable = true;
        ZWriteEnable = true;
        CullMode = None;
        AlphaBlendEnable = false;
        VertexShader = compile vs_3_0 VatVS();
        PixelShader = compile ps_3_0 VatPS();
    }
}
