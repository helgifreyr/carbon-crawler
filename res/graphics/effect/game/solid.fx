#include "common.fxh"

float4 LightDir < bool SasUiVisible = true; > = float4(0.4, 0.8, 0.3, 0.0);
float4 AmbientColor < bool SasUiVisible = true; > = float4(0.18, 0.2, 0.26, 1.0);
float4 EyePos < bool SasUiVisible = true; > = float4(0.0, 500.0, 1000.0, 1.0);

struct VSIn
{
    float3 pos : POSITION;
    float3 normal : NORMAL;
    float4 color : TEXCOORD0;
};

struct VSOut
{
    float4 pos : SV_Position;
    float3 normal : TEXCOORD0;
    float4 color : TEXCOORD1;
    float3 viewDir : TEXCOORD2;
};

VSOut SolidVS(VSIn i)
{
    VSOut o;
    float4 world = mul(float4(i.pos, 1.0), WorldMat);
    o.pos = mul(world, ViewProjectionMat);
    o.normal = mul(float4(i.normal, 0.0), WorldMat).xyz;
    o.color = i.color;
    o.viewDir = EyePos.xyz - world.xyz;
    return o;
}

float4 SolidPS(VSOut i) : SV_Target
{
    float3 n = normalize(i.normal);
    float diffuse = saturate(dot(n, normalize(LightDir.xyz)));
    float rim = pow(1.0 - saturate(abs(dot(n, normalize(i.viewDir)))), 3.0);
    float3 rgb = i.color.rgb * (AmbientColor.rgb + diffuse) + rim * 0.35;
    return float4(rgb, i.color.a);
}

technique Main
{
    pass P0
    {
        ZEnable = true;
        ZWriteEnable = true;
        CullMode = None;
        AlphaBlendEnable = false;
        VertexShader = compile vs_3_0 SolidVS();
        PixelShader = compile ps_3_0 SolidPS();
    }
}
