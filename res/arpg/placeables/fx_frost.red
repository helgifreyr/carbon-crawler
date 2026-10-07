type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/fx_burst96.cmf"
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
                    value: [0.550, 0.800, 1.000, 1.100]
                -   type: Tr2Vector4Parameter
                    name: "FxColorEnd"
                    value: [0.200, 0.450, 1.000, 1.000]
                -   type: Tr2Vector4Parameter
                    name: "FxSize"
                    value: [0.240, 0.120, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxMotion"
                    value: [23.413, 2.000, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxShape"
                    value: [0.750, 0.120, 0.250, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxBias"
                    value: [0.000, 0.000, 1.350, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "FxVary"
                    value: [0.900, 0.550, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
