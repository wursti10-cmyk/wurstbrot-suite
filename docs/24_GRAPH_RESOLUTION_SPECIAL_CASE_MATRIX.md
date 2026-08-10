# Graph Prerequisite Special Case Comparison

Each current comparison uses explicit evidence: hidden targets enable `include_hidden_legacy`; reqUnlock targets enable `assume_external_unlocks`. Folder ambiguity and missing source semantics remain unresolved.

Accuracy 9 hat alle 14 unresolved Hidden-Folder-Zeilen einzeln gegen Datamine, Legacy-Pfad und
Graphstatus revalidiert. Die Matrix bleibt fachlich unverändert; es wurde keine Folder-Heuristik
ergänzt. Details: [Partial Folder Research](29_PARTIAL_FOLDER_RESEARCH.md).

| Metric | Accuracy 3 | Accuracy 4 |
|---|---:|---:|
| Exact/resolved | 0 | 35 |
| Unresolved | 31 | 14 |
| Unsupported | 18 | 0 |
| Mismatch | 0 | 0 |

| Vehicle | hiddenResearch | reqUnlock | Folder | Previous | Current | Explicit evidence | Reason |
|---|---:|---|---|---|---|---|---|
| ab_205a_1 | no | ch_heli_unlocked_italy | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| ah_1g | no | ch_heli_unlocked_usa | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| ah_1g_iaf | no | ch_heli_unlocked_israel | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| b-17g_iaf | no | isr_air_unlocked | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| fiat_cr42 | yes | — | fiat_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| fiat_g50_seria2 | yes | — | fiat_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| fiat_g50_seria7as | yes | — | fiat_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| fr_amc_34 | no | unlocked_france_tank_2_era | fr_hotchkiss_fcm_group | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| fr_fcm_36 | no | unlocked_france_tank_2_era | fr_hotchkiss_fcm_group | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| fr_hotchkiss_h35 | no | unlocked_france_tank_2_era | fr_hotchkiss_fcm_group | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| fr_vtb11 | no | unlocked_france_boat_2_era | fr_vtb_group | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| fr_vtb14 | no | unlocked_france_boat_2_era | fr_vtb_group | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| fr_vtb8 | no | unlocked_france_boat_2_era | fr_vtb_group | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| germ_flakpanzer_V_Coelian | yes | — | — | unsupported | exact_match | include_hidden_legacy | Ordered prerequisite vehicle IDs are identical. |
| germ_ls_class | no | unlocked_germany_boat_2_era | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| germ_panther_II | yes | — | — | unsupported | exact_match | include_hidden_legacy | Ordered prerequisite vehicle IDs are identical. |
| germ_pzkpfw_Maus | yes | — | — | unsupported | exact_match | include_hidden_legacy | Ordered prerequisite vehicle IDs are identical. |
| germ_pzkpfw_VI_ausf_b_tiger_IIh_kwk46 | yes | — | — | unsupported | exact_match | include_hidden_legacy | Ordered prerequisite vehicle IDs are identical. |
| h_34_france | no | ch_heli_unlocked_france | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| hkp3c | no | ch_heli_unlocked_sweden | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| il_amx_13_75 | no | isr_tank_unlocked | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| il_m109 | no | isr_tank_unlocked | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| il_m_51 | no | isr_tank_unlocked | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| il_tcm_20 | no | isr_tank_unlocked | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| jp_t14_class | no | unlocked_japan_boat_2_era | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| jp_type_95_ha_go | no | unlocked_japan_tank_2_era | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| mc-202 | yes | — | mc200_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| mc200_serie3 | yes | — | mc200_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| mc200_serie7 | yes | — | mc200_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| mi_4av | no | ch_heli_unlocked_ussr | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| os2u_1 | no | unlocked_usa_ship_2_era | os2u_group | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| os2u_3 | no | unlocked_usa_ship_2_era | os2u_group | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| r2y2_kai | yes | — | r2y2_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| r2y2_v1 | yes | — | r2y2_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| r2y2_v2 | yes | — | r2y2_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| s_199 | no | isr_air_unlocked | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| sa_313b | no | ch_heli_unlocked_germany | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| scout_ah_mk1 | no | ch_heli_unlocked_britain | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| sm_79_1936 | yes | — | sm_79_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| sm_79_1939 | yes | — | sm_79_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| sm_79_1941 | yes | — | sm_79_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| sm_79_1943 | yes | — | sm_79_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| sm_79_iar | yes | — | sm_79_group | unsupported | unresolved_expected | include_hidden_legacy | Unresolved rule(s): FOLDER_MEMBERSHIP; explicit evidence does not resolve the remaining source ambiguity. |
| spitfire_mk9c_iaf | no | isr_air_unlocked | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| uh_1b_japan | no | ch_heli_unlocked_japan_1 | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| uk_destroyer_clemson_churchill | no | unlocked_britain_ship_2_era | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| uk_mtb_1series | no | unlocked_britain_boat_2_era | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| ussr_g5_mtb | no | unlocked_ussr_boat_2_era | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
| z_11wa | no | ch_heli_unlocked_china | — | unresolved_expected | exact_match | assume_external_unlocks | Ordered prerequisite vehicle IDs are identical. |
