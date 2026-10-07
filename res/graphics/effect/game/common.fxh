cbuffer PerFrameVS : register(b1)
{
    float4x4 ViewInverseTransposeMat;
    float4 SunDirWorld;
    float4 SceneFogColor;
    float4x4 ViewProjectionMat;
    float4x4 ViewMat;
    float4x4 ProjectionMat;
};

cbuffer PerObjectVS : register(b3)
{
    float4x4 WorldMat;
};
