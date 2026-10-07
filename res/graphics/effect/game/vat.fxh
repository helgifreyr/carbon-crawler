// Vertex animation textures: one column per vertex, one row per baked frame.
// VatState: (row A v, row B v, A->B blend, -); VatFade: the clip being faded to, w is the fade weight.
float4 VatState < bool SasUiVisible = true; > = float4(0.0, 0.0, 0.0, 0.0);
float4 VatFade < bool SasUiVisible = true; > = float4(0.0, 0.0, 0.0, 0.0);

texture2D VatPos;
sampler VatPosSampler = sampler_state
{
    Texture = <VatPos>;
    MinFilter = Point;
    MagFilter = Point;
    MipFilter = None;
    AddressU = Clamp;
    AddressV = Clamp;
};

float3 VatLookup(sampler s, float u)
{
    float3 a = lerp(tex2Dlod(s, float4(u, VatState.x, 0, 0)).xyz, tex2Dlod(s, float4(u, VatState.y, 0, 0)).xyz, VatState.z);
    float3 b = lerp(tex2Dlod(s, float4(u, VatFade.x, 0, 0)).xyz, tex2Dlod(s, float4(u, VatFade.y, 0, 0)).xyz, VatFade.z);
    return lerp(a, b, VatFade.w);
}
