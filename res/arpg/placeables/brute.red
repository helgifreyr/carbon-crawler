type: WodPlaceableRes
visualModel:
    type: Tr2Model
    meshes:
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/enemy.cmf"
        opaqueAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/vat.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "VatState"
                    value: [0.006, 0.006, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "VatFade"
                    value: [0.006, 0.006, 0.000, 0.000]
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
                    resourcePath: "res:/arpg/textures/char_enemy_brute.png"
                -   type: TriTextureParameter
                    name: "LightMap"
                    resourcePath: "res:/arpg/textures/torchlight.png"
                -   type: TriTextureParameter
                    name: "NormalMap"
                    resourcePath: "res:/arpg/textures/char_enemy_n.png"
                -   type: TriTextureParameter
                    name: "VatNrm"
                    resourcePath: "res:/arpg/anims/enemy_nrm.dds"
                -   type: TriTextureParameter
                    name: "VatPos"
                    resourcePath: "res:/arpg/anims/enemy_pos.dds"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/enemy_glow.cmf"
        opaqueAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/vat.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "VatState"
                    value: [0.006, 0.006, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "VatFade"
                    value: [0.006, 0.006, 0.000, 0.000]
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
                    resourcePath: "res:/arpg/textures/char_enemy_brute.png"
                -   type: TriTextureParameter
                    name: "LightMap"
                    resourcePath: "res:/arpg/textures/torchlight.png"
                -   type: TriTextureParameter
                    name: "NormalMap"
                    resourcePath: "res:/arpg/textures/char_enemy_n.png"
                -   type: TriTextureParameter
                    name: "VatNrm"
                    resourcePath: "res:/arpg/anims/enemy_nrm.dds"
                -   type: TriTextureParameter
                    name: "VatPos"
                    resourcePath: "res:/arpg/anims/enemy_pos.dds"
    -   type: Tr2Mesh
        geometryResPath: "res:/arpg/meshes/enemy_halo.cmf"
        transparentAreas:
        -   type: Tr2MeshArea
            effect:
                type: Tr2Effect
                effectFilePath: "res:/graphics/effect/game/halo_vat.fx"
                parameters:
                -   type: Tr2Vector4Parameter
                    name: "VatState"
                    value: [0.006, 0.006, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "VatFade"
                    value: [0.006, 0.006, 0.000, 0.000]
                -   type: Tr2Vector4Parameter
                    name: "HaloColor"
                    value: [1.000, 0.300, 0.100, 0.900]
                resources:
                -   type: TriTextureParameter
                    name: "DiffuseMap"
                    resourcePath: "res:/arpg/textures/halo.png"
                -   type: TriTextureParameter
                    name: "VatPos"
                    resourcePath: "res:/arpg/anims/enemy_pos.dds"
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
