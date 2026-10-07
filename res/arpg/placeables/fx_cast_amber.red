type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/fx_burst24.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/fx_burst.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "FxTime"
                    value: [0.000, 0.360, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxColor"
                    value: [1.000, 0.750, 0.300, 2.200]
                -   type: Tr2Vector4Parameter
                    name: "FxColorEnd"
                    value: [0.600, 0.300, 0.050, 1.000]
                -   type: Tr2Vector4Parameter
                    name: "FxSize"
                    value: [0.220, 0.030, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxMotion"
                    value: [3.400, 5.000, 1.500, 0.200]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
