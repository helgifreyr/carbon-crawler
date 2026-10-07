type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/fx_burst72.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/fx_burst.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "FxTime"
                    value: [0.000, 0.450, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxColor"
                    value: [1.000, 0.500, 0.160, 2.300]
                -   type: Tr2Vector4Parameter
                    name: "FxColorEnd"
                    value: [0.800, 0.100, 0.020, 1.000]
                -   type: Tr2Vector4Parameter
                    name: "FxSize"
                    value: [0.380, 0.180, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxMotion"
                    value: [21.565, 4.000, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxShape"
                    value: [1.000, 0.050, 1.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxVary"
                    value: [0.920, 0.850, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
