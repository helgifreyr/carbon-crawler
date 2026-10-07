type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/player.cmf"
        opaqueAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/vat.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "VatState"
                    value: [0.004, 0.004, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "VatFade"
                    value: [0.004, 0.004, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "Flash"
                    value: [0.000, 0.000, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "Tint"
                    value: [0.000, 0.000, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "Occlusion"
                    value: [0.550, -0.500, 0.750, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "Surface"
                    value: [0.500, 0.550, 24.000, 0.600]
                -   type: Tr2Vector4Parameter
                    name: "LightMapRect"
                    value: [-32.000, -24.000, 0.003, 0.021]
                -   type: Tr2Vector4Parameter
                    name: "LightScale"
                    value: [1.500, 0.000, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/char_player_self.png"
                -   type: TriTextureParameter
                    name: "LightMap"
                    resourcePath: "res:/arpg/textures/torchlight.png"
                -   type: TriTextureParameter
                    name: "NormalMap"
                    resourcePath: "res:/arpg/textures/char_player_n.png"
                -   type: TriTextureParameter
                    name: "VatNrm"
                    resourcePath: "res:/arpg/anims/player_nrm.dds"
                -   type: TriTextureParameter
                    name: "VatPos"
                    resourcePath: "res:/arpg/anims/player_pos.dds"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/player_glow.cmf"
        opaqueAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/vat.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "VatState"
                    value: [0.004, 0.004, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "VatFade"
                    value: [0.004, 0.004, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "Flash"
                    value: [0.000, 0.000, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "Tint"
                    value: [0.000, 0.000, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "Emissive"
                    value: [1.000, 0.300, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "LightMapRect"
                    value: [-32.000, -24.000, 0.003, 0.021]
                -   type: Tr2Vector4Parameter
                    name: "LightScale"
                    value: [1.500, 0.000, 0.000, 0.000]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/char_player_self.png"
                -   type: TriTextureParameter
                    name: "LightMap"
                    resourcePath: "res:/arpg/textures/torchlight.png"
                -   type: TriTextureParameter
                    name: "NormalMap"
                    resourcePath: "res:/arpg/textures/char_player_n.png"
                -   type: TriTextureParameter
                    name: "VatNrm"
                    resourcePath: "res:/arpg/anims/player_nrm.dds"
                -   type: TriTextureParameter
                    name: "VatPos"
                    resourcePath: "res:/arpg/anims/player_pos.dds"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/player_halo.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/halo_vat.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "VatState"
                    value: [0.004, 0.004, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "VatFade"
                    value: [0.004, 0.004, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "HaloColor"
                    value: [0.250, 1.000, 0.450, 0.800]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
                -   type: TriTextureParameter
                    name: "VatPos"
                    resourcePath: "res:/arpg/anims/player_pos.dds"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/shadow.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/blob.fx"
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/blob.png"
