type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/fx_burst22.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/fx_burst.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "FxTime"
                    value: [0.000, 0.500, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxColor"
                    value: [0.350, 0.600, 1.000, 2.200]
                -   type: Tr2Vector4Parameter
                    name: "FxColorEnd"
                    value: [0.050, 0.150, 0.600, 1.000]
                -   type: Tr2Vector4Parameter
                    name: "FxSize"
                    value: [0.180, 0.030, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxMotion"
                    value: [2.200, 3.000, 3.000, 1.600]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
