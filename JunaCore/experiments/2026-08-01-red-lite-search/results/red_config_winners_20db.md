# Red per-path effective-rate configuration search (JunaCore, LFM sync)

Frame-harness search at 20 dB: one-second CRC-16 frames, multi-start (native + 2 corners) two-pass coordinate descent over N, CP (to 128), LDPC rate, pilot spacings, check degree, and coding horizon; 20-frame screen at seed 5, finalists confirmed on 60 frames at unseen seeds 6 and 7 and ranked by mean effective rate across both seeds. Acquisition is the package LFM sync; rates are not comparable with the sonique winners table (P2).

| Path | Receiver | N | CP | Rate | Pilots | dc | K | Mean bit/s | Min bit/s | Mean PSR | BER |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red1 lane 1 | standard | 512 | 16 | 0.5 | 3/4 | 10 | fill | 1922.9 | 1880.1 | 0.75 | 0.00445288 |
| red1 lane 2 | lite | 2048 | 64 | 0.5 | 3/4 | 8 | 4 | 1995.7 | 1918.0 | 0.6417 | 0.00647761 |
| red1 lane 3 | lite | 2048 | 128 | 0.5 | 5/10 | 8 | 4 | 3625.3 | 3588.6 | 0.825 | 0.00376771 |
| red2 lane 1 | standard | 512 | 32 | 0.25 | 3/10 | 10 | fill | 1280.1 | 1204.8 | 0.85 | 0.000155971 |
| red2 lane 2 | standard | 512 | 32 | 0.5 | 3/5 | 10 | fill | 2062.3 | 2017.4 | 0.7667 | 0.01967 |
| red2 lane 3 | standard | 512 | 32 | 0.5 | 3/10 | 10 | fill | 2422.6 | 2321.6 | 0.8 | 0.0149241 |
| red3 lane 1 | standard | 512 | 32 | 0.5 | 3/10 | 10 | fill | 2498.3 | 2473.0 | 0.825 | 0.010123 |
| red3 lane 2 | standard | 512 | 16 | 0.5 | 5/10 | 10 | fill | 2994.7 | 2994.7 | 0.8 | 0.0131451 |
| red3 lane 3 | standard | 512 | 16 | 0.5 | 5/10 | 8 | fill | 3119.5 | 2994.7 | 0.8333 | 0.00533598 |
| red4 lane 1 | standard | 512 | 16 | 0.5 | 5/10 | 10 | fill | 3618.6 | 3556.2 | 0.9667 | 0.0013585 |
| red4 lane 2 | standard | 512 | 0 | 0.5 | 5/10 | 10 | fill | 3173.6 | 3046.7 | 0.8333 | 0.00837208 |
| red4 lane 3 | standard | 512 | 16 | 0.5 | 5/10 | 10 | fill | 3587.4 | 3493.8 | 0.9583 | 0.00178246 |
