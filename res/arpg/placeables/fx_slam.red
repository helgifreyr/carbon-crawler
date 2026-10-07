type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/fx_burst48.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/fx_burst.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "FxTime"
                    value: [0.000, 0.600, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxColor"
                    value: [0.750, 0.600, 0.450, 1.200]
                -   type: Tr2Vector4Parameter
                    name: "FxColorEnd"
                    value: [0.350, 0.280, 0.220, 1.000]
                -   type: Tr2Vector4Parameter
                    name: "FxSize"
                    value: [0.500, 0.220, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxMotion"
                    value: [11.486, 3.300, 1.000, 0.100]
                -   type: Tr2Vector4Parameter
                    name: "FxShape"
                    value: [1.000, 0.100, 1.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxVary"
                    value: [0.900, 0.800, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
