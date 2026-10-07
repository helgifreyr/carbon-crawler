type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/fx_burst64.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/fx_burst.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "FxTime"
                    value: [0.000, 0.900, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxColor"
                    value: [1.000, 0.850, 0.350, 2.400]
                -   type: Tr2Vector4Parameter
                    name: "FxColorEnd"
                    value: [1.000, 0.500, 0.100, 1.000]
                -   type: Tr2Vector4Parameter
                    name: "FxSize"
                    value: [0.260, 0.050, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxMotion"
                    value: [4.500, 2.000, 1.500, 1.400]
                -   type: Tr2Vector4Parameter
                    name: "FxShape"
                    value: [1.000, 0.300, 1.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
