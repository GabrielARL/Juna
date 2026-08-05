# Red per-path effective-rate configuration search (JunaCore, LFM sync)

Frame-harness search at 20 dB: one-second CRC-16 frames, multi-start (native + 2 corners) two-pass coordinate descent over N, CP (to 128), LDPC rate, pilot spacings, check degree, and coding horizon; 20-frame screen at seed 5, finalists confirmed on 60 frames at unseen seeds 6 and 7 and ranked by mean effective rate across both seeds. Acquisition is the package LFM sync; rates are not comparable with the sonique winners table (P2).

| Path | Receiver | N | CP | Rate | Pilots | dc | K | Mean bit/s | Min bit/s | Mean PSR | BER |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| red1 hydrophone 1 | pfft | 2048 | 32 | 0.25 | 3/10 | 10 | 4 | 1143.9 | 1096.9 | 0.6083 | 0.000376919 |
| red1 hydrophone 2 | pfft | 2048 | 32 | 0.25 | 3/8 | 10 | 4 | 1081.5 | 1005.3 | 0.5917 | 0.000282008 |
| red1 hydrophone 3 | pfft | 2048 | 128 | 0.5 | 5/5 | 10 | 4 | 2472.9 | 2407.8 | 0.6333 | 0.0281438 |
| red2 hydrophone 1 | pfft | 2048 | 0 | 0.25 | 3/5 | 10 | 2 | 282.7 | 272.2 | 0.225 | 0.0209499 |
| red2 hydrophone 2 | pfft | 1024 | 32 | 0.25 | 3/10 | 10 | 2 | 468.5 | 430.1 | 0.5083 | 0.00602629 |
| red2 hydrophone 3 | pfft | 2048 | 0 | 0.25 | 5/5 | 10 | 4 | 658.9 | 540.6 | 0.325 | 0.00104689 |
| red3 hydrophone 1 | pfft | 2048 | 32 | 0.125 | 5/8 | 10 | fill | 297.6 | 270.5 | 0.3667 | 0.00255492 |
| red3 hydrophone 2 | pfft | 2048 | 128 | 0.25 | 5/10 | 10 | fill | 935.0 | 907.5 | 0.5667 | 0.000924013 |
| red3 hydrophone 3 | pfft | 2048 | 16 | 0.25 | 5/8 | 10 | fill | 796.7 | 714.2 | 0.4833 | 0.00117446 |
| red4 hydrophone 1 | pfft | 2048 | 32 | 0.25 | 5/10 | 10 | 4 | 1637.4 | 1505.7 | 0.725 | 0.000151204 |
| red4 hydrophone 2 | pfft | 2048 | 16 | 0.25 | 5/5 | 10 | 4 | 1378.2 | 1344.6 | 0.6833 | 0.000179833 |
| red4 hydrophone 3 | pfft | 2048 | 128 | 0.5 | 5/10 | 10 | 2 | 1106.4 | 1051.1 | 0.3333 | 0.100485 |
