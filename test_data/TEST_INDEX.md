# AdScope Test Dataset Index

This directory contains 30 CSV test datasets for validating the AdScope insight engine across various scenarios.

## Clean English Datasets (t01-t05)

### t01_clean_en_single_campaign.csv
- **Purpose**: Single campaign with clear device/platform performance differences
- **Expected Insight**: Mobile outperforms Desktop, Google outperforms Facebook
- **Signal Strength**: Strong insights expected
- **Rows**: 14

### t02_clean_en_multi_campaign.csv
- **Purpose**: Multiple campaigns with clear under/overperformance
- **Expected Insight**: Spring Launch and Summer Sale outperform Winter Promo significantly
- **Signal Strength**: Strong insights expected
- **Rows**: 15

### t03_clean_en_platform_device.csv
- **Purpose**: Strong Google vs Facebook and Mobile vs Desktop differences
- **Expected Insight**: Google outperforms Facebook, Mobile outperforms Desktop
- **Signal Strength**: Strong insights expected
- **Rows**: 14

### t04_clean_en_budget_imbalance.csv
- **Purpose**: Severe budget misallocation - Google gets 90%+ of spend but Facebook underperforms
- **Expected Insight**: Budget allocation imbalance, Facebook underutilized
- **Signal Strength**: Strong insights expected
- **Rows**: 14

### t05_clean_en_ctr_high_cvr_low.csv
- **Purpose**: High CTR but low conversion rate - traffic quality issue
- **Expected Insight**: High click volume but poor conversion efficiency
- **Signal Strength**: Moderate insights expected
- **Rows**: 14

## Clean Hebrew Datasets (t06-t10)

### t06_clean_he_single_campaign.csv
- **Purpose**: Single campaign with Hebrew column names and labels
- **Expected Insight**: Mobile outperforms Desktop, Google outperforms Facebook
- **Signal Strength**: Strong insights expected
- **Rows**: 14

### t07_clean_he_multi_campaign.csv
- **Purpose**: Multiple campaigns with Hebrew labels
- **Expected Insight**: מבצע קיץ and השקה אביב outperform מבצע חורף
- **Signal Strength**: Strong insights expected
- **Rows**: 15

### t08_clean_he_platform_device.csv
- **Purpose**: Platform and device performance differences with Hebrew labels
- **Expected Insight**: Google outperforms Facebook, Mobile outperforms Desktop
- **Signal Strength**: Strong insights expected
- **Rows**: 14

### t09_clean_he_budget_imbalance.csv
- **Purpose**: Budget misallocation with Hebrew labels
- **Expected Insight**: Budget allocation imbalance
- **Signal Strength**: Strong insights expected
- **Rows**: 14

### t10_clean_he_weekend_drop.csv
- **Purpose**: Weekend performance drop pattern with Hebrew labels
- **Expected Insight**: Weekend days (Sat/Sun) show significantly lower performance
- **Signal Strength**: Strong insights expected
- **Rows**: 14

## Mixed Language Datasets (t11-t15)

### t11_mixed_lang_campaigns.csv
- **Purpose**: Campaign names mix Hebrew and English
- **Expected Insight**: Performance differences across campaigns
- **Signal Strength**: Strong insights expected
- **Rows**: 14

### t12_mixed_lang_platforms.csv
- **Purpose**: Platform names mix Hebrew (גוגל, פייסבוק) and English
- **Expected Insight**: Google/גוגל outperforms Facebook/פייסבוק
- **Signal Strength**: Strong insights expected
- **Rows**: 14

### t13_mixed_lang_devices.csv
- **Purpose**: Device labels mix Hebrew (נייד, דסקטופ) and English
- **Expected Insight**: Mobile/נייד vs Desktop/דסקטופ performance differences
- **Signal Strength**: Strong insights expected
- **Rows**: 14

### t14_mixed_lang_schema.csv
- **Purpose**: Hebrew column headers with mixed English/Hebrew data values
- **Expected Insight**: Performance patterns across campaigns/platforms/devices
- **Signal Strength**: Strong insights expected
- **Rows**: 14

### t15_mixed_lang_time_series.csv
- **Purpose**: Time series with mixed language campaign names
- **Expected Insight**: Temporal patterns with multilingual labels
- **Signal Strength**: Moderate insights expected
- **Rows**: 14

## Noisy / Gibberish Datasets (t16-t20)

### t16_noisy_labels_case_mix.csv
- **Purpose**: Inconsistent casing (Mobile/mobile/MOBILE, Google/google/GOOGLE)
- **Expected Insight**: Should normalize and detect performance patterns
- **Signal Strength**: Strong insights expected (after normalization)
- **Rows**: 14

### t17_noisy_schema_typos.csv
- **Purpose**: Typos in platform/device names (G00gle, Facebok, Moblie, Deskto)
- **Expected Insight**: Should handle typos and detect patterns
- **Signal Strength**: Moderate insights expected
- **Rows**: 14

### t18_noisy_gibberish_headers.csv
- **Purpose**: Alternative column names (Date, Campaign Name, Media Cost, etc.)
- **Expected Insight**: Should map schema and detect performance patterns
- **Signal Strength**: Strong insights expected (after schema mapping)
- **Rows**: 14

### t19_noisy_sparse_values.csv
- **Purpose**: Missing values in some rows (empty spend, revenue, clicks)
- **Expected Insight**: Should handle missing data gracefully
- **Signal Strength**: Moderate insights expected
- **Rows**: 14

### t20_noisy_high_cardinality.csv
- **Purpose**: Many unique campaigns (A through M) with limited data per campaign
- **Expected Insight**: May struggle with high cardinality, should aggregate or focus on platform/device
- **Signal Strength**: Weak to moderate insights expected
- **Rows**: 14

## Business Pattern Tests (t21-t25)

### t21_pattern_budget_misallocation.csv
- **Purpose**: Extreme budget misallocation - Google gets 95%+ of spend
- **Expected Insight**: Severe budget imbalance, Facebook underutilized despite good performance
- **Signal Strength**: Very strong insights expected
- **Rows**: 14

### t22_pattern_winning_campaign.csv
- **Purpose**: One campaign (Summer Sale) significantly outperforms others
- **Expected Insight**: Summer Sale is the clear winner with 4x ROAS vs others
- **Signal Strength**: Very strong insights expected
- **Rows**: 14

### t23_pattern_losing_campaign.csv
- **Purpose**: One campaign (Winter Promo) significantly underperforms
- **Expected Insight**: Winter Promo is losing money, should pause or optimize
- **Signal Strength**: Very strong insights expected
- **Rows**: 14

### t24_pattern_mobile_underperform.csv
- **Purpose**: Mobile consistently underperforms Desktop across all campaigns
- **Expected Insight**: Mobile conversion rate is 50% lower than Desktop
- **Signal Strength**: Very strong insights expected
- **Rows**: 14

### t25_pattern_desktop_outperform.csv
- **Purpose**: Desktop consistently outperforms Mobile significantly
- **Expected Insight**: Desktop generates 2x ROAS compared to Mobile
- **Signal Strength**: Very strong insights expected
- **Rows**: 14

## Temporal / Edge Cases (t26-t30)

### t26_temporal_weekend_drop.csv
- **Purpose**: Clear weekend performance drop pattern
- **Expected Insight**: Weekend days show 50% lower ROAS than weekdays
- **Signal Strength**: Strong insights expected
- **Rows**: 14

### t27_temporal_gradual_decline.csv
- **Purpose**: Gradual ROAS decline over time
- **Expected Insight**: Performance declining week over week, needs attention
- **Signal Strength**: Moderate to strong insights expected
- **Rows**: 14

### t28_temporal_recovery_pattern.csv
- **Purpose**: Performance drops then recovers
- **Expected Insight**: Recovery pattern after weak period
- **Signal Strength**: Moderate insights expected
- **Rows**: 14

### t29_edge_small_dataset.csv
- **Purpose**: Very small dataset (4 rows)
- **Expected Insight**: Should return no insights (dataset too small)
- **Signal Strength**: No insights expected (edge case)
- **Rows**: 4

### t30_edge_no_strong_signal.csv
- **Purpose**: All campaigns/platforms/devices perform nearly identically
- **Expected Insight**: No strong signals, all segments perform similarly
- **Signal Strength**: Weak or no insights expected
- **Rows**: 14

## Usage Notes

- All datasets use realistic marketing campaign data structure
- Column names vary: some use standard names (date, campaign, platform, device, spend, revenue), others use alternatives (תאריך, קמפיין, עלות, הכנסה, etc.)
- Values are internally consistent within each dataset
- Some datasets intentionally include noise to test robustness
- Edge cases (t29, t30) are designed to test graceful handling of weak/no signals
