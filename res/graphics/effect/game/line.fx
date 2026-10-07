#include "common.fxh"

struct VSIn
{
    float3 pos : POSITION;
    float4 color : TEXCOORD0;
};

struct VSOut
{
    float4 pos : SV_Position;
    float4 color : TEXCOORD0;
};

VSOut LineVS(VSIn i)
{
    VSOut o;
    o.pos = mul(mul(float4(i.pos, 1.0), WorldMat), ViewProjectionMat);
    o.color = i.color;
    return o;
}

float4 LinePS(VSOut i) : SV_Target
{
    return i.color;
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
        VertexShader = compile vs_3_0 LineVS();
        PixelShader = compile ps_3_0 LinePS();
    }
}
