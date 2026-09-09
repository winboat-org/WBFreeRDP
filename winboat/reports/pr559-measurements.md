# PR559 measurement ledger

AVC counts cover the connection log; CPU/GPU counters cover the sampling window. A configured VAAPI overlay does not prove hardware decoding occurred. Positive GPU decode time does. Invalid markers are rejected samples, not automatically visible corruption.

| Case | Visible FPS | p95 gap ms | >100 ms stalls | Invalid / samples | AVC420 commands | GPU decode ms |
|---|---:|---:|---:|---:|---:|---:|
| baseline-repeat-2 | 31.73 | 50.6 | 0 | 4 / 3954 | 0 | 0.0 |
| baseline-simple | 31.74 | 60.6 | 0 | 0 / 3954 | 0 | 0.0 |
| frame-only-motion-1 | 57.02 | 35.4 | 0 | 0 / 3953 | 0 | 0.0 |
| frame-only-motion-2 | 54.47 | 35.4 | 0 | 0 / 3950 | 0 | 0.0 |
| frame-only-simple | 58.72 | 30.4 | 0 | 0 / 3954 | 0 | 0.0 |
| full-motion-1 | 57.23 | 35.4 | 0 | 9 / 3953 | 0 | 0.0 |
| full-motion-2 | 55.18 | 35.4 | 0 | 0 / 3953 | 0 | 0.0 |
| full-simple | 57.28 | 30.4 | 0 | 0 / 3954 | 0 | 0.0 |
| restored-motion | 31.74 | 45.5 | 0 | 0 / 3952 | 0 | 0.0 |
| baseline-native-software | 31.61 | 55.7 | 0 | 28 / 3954 | 651 | 0.0 |
| baseline-native-onecpu | 31.58 | 60.7 | 0 | 21 / 3952 | 651 | 0.0 |
| frame-only-native-vaapi | 51.42 | 40.4 | 0 | 0 / 3950 | 0 | 0.0 |
| frame-only-native-software | 41.16 | 45.5 | 0 | 26 / 3952 | 829 | 0.0 |
| frame-only-native-onecpu | 42.69 | 45.5 | 0 | 18 / 3953 | 921 | 0.0 |
| full-native-vaapi | 53.17 | 35.4 | 0 | 0 / 3952 | 0 | 0.0 |
| full-native-software | 50.95 | 40.5 | 1 | 11 / 3952 | 0 | 0.0 |
| full-native-onecpu | 46.00 | 45.5 | 0 | 6 / 3953 | 448 | 0.0 |
| restored-native-vaapi | 31.74 | 45.5 | 0 | 0 / 3953 | 0 | 0.0 |
| repeat-0-full-software | 52.27 | 35.4 | 0 | 2 / 5929 | 0 | 0.0 |
| repeat-0-full-vaapi | 43.90 | 45.5 | 0 | 28 / 5926 | 1148 | 1039.5 |
| repeat-1-frame-only-software | 52.59 | 35.4 | 0 | 0 / 5927 | 0 | 0.0 |
| repeat-1-frame-only-vaapi | 47.54 | 40.5 | 0 | 26 / 5927 | 504 | 453.5 |
| repeat-2-full-software | 52.91 | 35.4 | 1 | 0 / 5927 | 0 | 0.0 |
| repeat-2-full-vaapi | 41.71 | 50.6 | 1 | 33 / 5927 | 1296 | 1173.5 |
| repeat-3-frame-only-software | 53.85 | 35.4 | 0 | 0 / 5927 | 0 | 0.0 |
| repeat-3-frame-only-vaapi | 42.18 | 50.6 | 0 | 56 / 5928 | 1133 | 1021.9 |
