#include "common.fxh"

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
};

VSOut BlobVS(VSIn i)
{
    VSOut o;
    o.pos = mul(mul(float4(i.pos, 1.0), WorldMat), ViewProjectionMat);
    o.uv = i.uv;
    return o;
}

float4 BlobPS(VSOut i) : SV_Target
{
    return tex2D(DiffuseSampler, i.uv);
}

technique Main
{
    pass P0
    {
        ZEnable = true;
        ZWriteEnable = false;
        CullMode = None;
        AlphaBlendEnable = true;
        SrcBlend = SrcAlpha;
        DestBlend = InvSrcAlpha;
        VertexShader = compile vs_3_0 BlobVS();
        PixelShader = compile ps_3_0 BlobPS();
    }
}
