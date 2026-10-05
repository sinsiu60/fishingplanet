# 🎵 음악 프롬프트

AI 작곡 도구(Suno, Udio 등)에 넣을 프롬프트 모음. 만든 파일을 `data/music/`에 **정해진 이름**으로 넣으면
게임이 알아서 재생한다 (코드 수정 필요 없음, 없는 곡은 그냥 무음).

## 0. 공통 규칙

### 넣는 법
| 칸 | 넣을 것 |
|---|---|
| Style / 스타일 | 각 곡의 **Style** 영어 문단 그대로 |
| Exclude / 제외 스타일 (Suno) · Negative (Udio) | 각 곡의 **Exclude** + 아래 공통 제외 |
| 가사 | 비움 + **Instrumental(연주곡) 켜기** |
| 길이 | 2~3분이면 충분 (게임에서 반복 재생) |

**공통 제외 (모든 곡 Exclude에 추가)**
```
vocals, lyrics, singing, spoken word, rap, fade out ending, crowd noise, vinyl crackle, sound effects
```

### 왜 이런 규칙이 있나 (이 게임만의 사정)
- 이 게임은 **소리로 물고기를 읽는다**: 물보라(돌진), 기포(점프), 긁힘(방향 전환), 끼익(줄 한계).
  이 소리들이 고음~중고음 대역이라, 음악은 **하이햇 연타·화이트노이즈·쉬익거리는 신스를 피하고**
  중저음 위주로 만든다. 프롬프트마다 "sparse high end"가 들어간 이유.
- 반복 재생되므로 **페이드아웃 엔딩 금지**. 끝이 자연스럽게 처음으로 돌아가는 버전을 고른다.
- 평상시 음악과 파이팅 음악은 **같은 악기 계열**로 맞춰 두어, 입질 → 파이팅 전환이 같은 곳의 다른 얼굴처럼 들리게 한다.
- 전설 테마는 화면이 금빛/보랏빛으로 물드는 보스전이다. 전설마다 성격이 다르다 (아래 표 참고).

### 파일 정리
1. 여러 번 생성해서 **가장 루프가 자연스러운 버전**을 고른다 (끝 2초와 처음 2초를 이어 들어보기).
2. 끝이 페이드아웃이면 Audacity로 잘라낸다 (마지막 마디 끝에서 자르기).
3. **OGG로 저장** (Audacity: 파일 → 내보내기 → OGG, 품질 5). mp3·wav도 되지만 ogg가 가볍고 루프가 깔끔하다.
4. 볼륨을 대충 맞춘다: Audacity `효과 → 음량 → 라우드니스 정규화` **-16 LUFS** (전 곡 동일).
5. `data/music/`에 아래 파일 이름으로 넣는다 → 그대로 `build.bat` 하면 exe에도 포함된다.

### 재생 규칙 (게임 쪽)
| 상황 | 재생 | 파일 없을 때 |
|---|---|---|
| 낚시터에서 대기·캐스팅·입질 | `spot_<낚시터>` | 무음 (환경음만) |
| 물고기가 물어 파이팅~뜰채 | `fight_<낚시터>` | 무음 |
| 전설이 다가오거나 파이팅 중 | `legend_<물고기>` | 코드로 만든 기본 전설 BGM |
| 타이틀 / 엔딩 (보너스) | `title` / `ending` | 무음 / 코드로 만든 엔딩 BGM |

곡이 바뀔 때는 0.9초 페이드아웃 → 1.2초 페이드인으로 넘어간다.

---

## 1. 낚시터 평상시 음악 (6곡)

조용히 기다리는 시간의 음악. 환경음(물소리·파도·빗소리)이 함께 깔리니 **비어 있는 듯 담백하게**.

### `spot_reservoir` — 동네 저수지
> 모든 낚시꾼의 시작. 낮은 산에 둘러싸인 잔잔한 저수지, 한가한 오후.

**Style**
```
Cozy acoustic lo-fi for a pixel-art fishing game, calm countryside reservoir on a lazy afternoon. Warm fingerpicked acoustic guitar, soft Rhodes piano chords, gentle upright bass, light brushed drums, occasional glockenspiel sparkle. 78 BPM, F major, relaxed and nostalgic, lots of space, sparse high end, seamless loop, instrumental.
```
**Exclude** `electric guitar distortion, heavy drums, trap hi-hats, EDM`

### `spot_valley` — 계곡
> 높은 바위산 사이 맑은 계곡물. 상쾌하고 차가운 공기.

**Style**
```
Fresh and airy Korean-inspired ambient folk, clear mountain stream between tall rocky peaks. Breathy daegeum bamboo flute melody, plucked gayageum patterns, soft kalimba, light hand percussion, wide reverb. 72 BPM, pentatonic, D major, peaceful, crisp morning air, sparse high end, seamless loop, instrumental.
```
**Exclude** `heavy drums, synth bass, rock, EDM, chinese erhu solo`

### `spot_breakwater` — 바다 방파제
> 등대가 서 있는 방파제. 갈매기, 바닷바람, 항구의 느긋함.

**Style**
```
Breezy seaside bossa nova for a fishing game, harbor breakwater with a lighthouse, salty wind. Nylon-string guitar comping, mellow electric piano, soft muted trumpet melody, light shaker and rim clicks, warm bass. 92 BPM, G major, sunny and laid-back, sparse high end, seamless loop, instrumental.
```
**Exclude** `heavy drums, distorted guitar, dubstep, loud cymbals`

### `spot_offshore` — 먼바다 배낚시
> 배를 타고 나간 먼바다. 끝없는 수평선, 흔들리는 갑판.

**Style**
```
Gentle sea-shanty waltz in 3/4, small fishing boat far out on the open ocean, endless horizon, rocking deck. Accordion, acoustic guitar, warm cello, soft fiddle melody, low frame drum on the downbeat. 96 BPM, D major, adventurous yet calm, a sense of vast distance, sparse high end, seamless loop, instrumental.
```
**Exclude** `rock drums, EDM, heavy brass, distortion`

### `spot_deep` — 심해
> 밤바다 배 조명 아래. 빛을 모르는 물고기들이 사는 깊은 곳.

**Style**
```
Dark calm deep-sea ambient, night fishing under a single boat lamp above a black abyss. Slow sparse felt piano notes, warm analog pads, deep sub-bass drones, distant sonar-like pings, subtle whale-like synth swells. 60 BPM, A minor, mysterious but peaceful, lots of silence, no percussion, sparse high end, seamless loop, instrumental.
```
**Exclude** `drums, beats, horror screams, jump scare, bright synth leads`

### `spot_secret` — 용문 폭포 (비밀 장소)
> 다섯 전설을 낚은 자만 오는 달빛 폭포. 신성하고 고요하다.

**Style**
```
Mystical sacred ambient, hidden moonlit waterfall from Korean legend, the place where carp become dragons. Gentle gayageum arpeggios, harp, celesta, soft wordless choir pad, low taiko heartbeat very far away. 66 BPM, E minor pentatonic, reverent, magical, shimmering, sparse high end, seamless loop, instrumental.
```
**Exclude** `pop drums, EDM, rock, vocals with lyrics`

---

## 2. 낚시터별 파이팅 음악 (6곡)

물고기가 물고 버티는 1~3분. **긴장감 + 리듬감**, 하지만 물고기 신호음(물보라·기포·긁힘)이 묻히지 않게
중저음 중심. 같은 낚시터 평상시 음악과 악기 계열을 맞췄다.

### `fight_reservoir` — 저수지 파이팅
**Style**
```
Upbeat folk-rock chase for a fishing game battle, lively and playful tension at a countryside reservoir. Driving strummed acoustic guitar, banjo riffs, punchy kick and snare, walking bass, hand claps on the backbeat. 140 BPM, F major with minor turns, energetic and fun, mid-range focused, sparse high end, no hi-hat spam, seamless loop, instrumental.
```
**Exclude** `heavy metal, EDM drops, trap hi-hats, slow tempo`

### `fight_valley` — 계곡 파이팅
**Style**
```
Korean fusion rock battle, struggling against a fish among river rocks. Fast gayageum riffs trading with overdriven electric guitar, janggu and buk drums driving the rhythm, daegeum stabs, tight bass. 150 BPM, D minor pentatonic, fierce and agile, mid-range focused, sparse high end, seamless loop, instrumental.
```
**Exclude** `EDM, trap, ballad, slow`

### `fight_breakwater` — 방파제 파이팅
**Style**
```
Surf rock fishing battle by the sea wall, reverb-drenched twangy guitar melody, tremolo picking, rolling toms, upright bass slap, bright organ stabs. 160 BPM, E minor, thrilling seaside chase, retro 60s energy, mid-range focused, sparse high end, seamless loop, instrumental.
```
**Exclude** `EDM, heavy metal screaming, trap hi-hats, slow`

### `fight_offshore` — 먼바다 파이팅
**Style**
```
Epic sea-shanty action, battling a huge fish from a rocking boat in open ocean. Driving fiddle and accordion melody, low brass swells, galloping cellos ostinato, big floor toms and frame drum, stomping rhythm. 145 BPM, D minor, heroic struggle against the sea, mid-range focused, sparse high end, seamless loop, instrumental.
```
**Exclude** `EDM, trap, pop vocals, slow`

### `fight_deep` — 심해 파이팅
**Style**
```
Tense dark synth thriller, something heavy pulling from the black abyss. Pulsing analog sub-bass ostinato, low metallic percussion hits, deep taiko, eerie cello tremolo, slow-rising synth pads. 120 BPM, A minor, ominous and relentless, low-end focused, very sparse high end, no hi-hats, seamless loop, instrumental.
```
**Exclude** `bright melodies, happy, EDM drops, dubstep wobble, horror screams`

### `fight_secret` — 용문 폭포 파이팅
**Style**
```
Mystical epic battle at a sacred moonlit waterfall. Thundering taiko and buk drums, urgent string ostinato, cascading gayageum and harp runs, soft wordless choir swells, daegeum calls. 140 BPM, E minor, majestic and urgent, mid-range focused, sparse high end, seamless loop, instrumental.
```
**Exclude** `EDM, rock drum kit, trap, pop`

---

## 3. 전설 테마 (6곡)

보스전. 화면이 물들고 3페이즈로 바뀐다. 각 전설의 **성격**과 **3페이즈 기믹**을 음악에 담았다.
곡 하나에 "고요한 등장 → 본격 전투 → 절정" 흐름이 들어가도록 구조를 적어두었다
(게임은 곡을 처음부터 반복하므로, 등장 부분이 짧은 버전을 고르면 좋다).

### `legend_golden_carp` — 황금잉어 '누렁이' (저수지)
> 비 오는 저녁, 황금 떡밥에만 반응. 좌우로 휘젓고, 방향을 두 번씩 바꾸고, **지친 척을 한다** — 장난꾸러기 보스.

**Style**
```
Mischievous majestic boss theme for a legendary golden carp, rainy evening at a countryside reservoir. Playful pizzicato strings and gayageum trading tricky syncopated phrases, warm brass fanfare, bouncing upright bass, punchy folk drums, sudden fake-out pauses then explosive returns. 132 BPM, D dorian, cheeky and grand, golden shimmer, mid-range focused, sparse high end, seamless loop, instrumental.
```
**Exclude** `horror, dark ambient, EDM, metal`

### `legend_tiger_mandarin` — 산신 쏘가리 '범' (계곡)
> 폭풍 치는 밤 계곡의 호랑이 무늬 쏘가리. 산신령. 바위에서 바위로 숨고 도주하자마자 뛰어오른다.

**Style**
```
Fierce Korean shamanic battle theme, a mountain-god tiger fish in a stormy night valley. Thunderous buk and janggu drums in a gutgeori rhythm, piercing piri double-reed melody, crashing jing gong, growling low brass, distorted bass undertow, sudden rhythmic breaks like a tiger pouncing. 140 BPM, C minor pentatonic, wild, primal and sacred, mid-range focused, sparse high end, seamless loop, instrumental.
```
**Exclude** `pop, happy, EDM, synthwave, chinese erhu`

### `legend_silver_bass` — 은빛 농어 '일렉트로' (방파제)
> 번개가 칠 때마다 뛰어오르는 은빛 농어. 두 번 연속 점프, 3페이즈에선 번개마다 점프.

**Style**
```
Electrifying boss theme for a silver sea bass that leaps with every lightning strike, stormy breakwater at night. Fast surf-rock guitar riffs over driving drum and bass breakbeat, sharp orchestral stabs like thunder cracks, pulsing synth bass, metallic shimmer accents on the downbeats. 168 BPM, F sharp minor, flashing, fast and thrilling, mid-range focused, avoid busy hi-hats, seamless loop, instrumental.
```
**Exclude** `slow, ballad, lo-fi, dubstep wobble, vocals`

### `legend_marlin` — 청새치 '일섬' (먼바다)
> 창 같은 주둥이를 가진 바다의 왕. 바다 끝까지 질주하고, 3페이즈엔 꼬리로 수면을 세 번 내려친다.

**Style**
```
Heroic epic orchestral duel at sea, an old fisherman versus the king of the ocean, a giant marlin. Soaring French horn and trumpet theme, galloping low strings ostinato, massive timpani and taiko, sweeping violins, rhythmic triple hits (three heavy accents) as a recurring motif. 150 BPM, D minor to D major climax, vast, noble, relentless, cinematic, mid-range focused, sparse high end, seamless loop, instrumental.
```
**Exclude** `EDM, rock drum kit, pop, lo-fi`

### `legend_coelacanth` — 실러캔스 '고대' (심해)
> 심연에서 올라온 살아있는 화석. **2페이즈엔 그림자·기포·판정 원이 사라져 소리로만 읽어야 한다** → 이 곡은 특히 비어 있어야 한다.

**Style**
```
Ancient abyssal boss theme, a living fossil rising from the deep ocean trench. Slow heavy half-time groove, deep pipe organ chords, low wordless male choir, massive sub-bass drones, distant cavernous drum hits, eerie glass harmonica, long silences between phrases. 90 BPM half-time, B flat minor, primordial, crushing pressure, awe and dread, very sparse high end, no hi-hats, seamless loop, instrumental.
```
**Exclude** `bright, happy, fast drums, EDM, rock, jump scare`

### `legend_dragon_carp` — 용문잉어 '등용' (용문 폭포, 최종 보스)
> 폭포를 거슬러 올라 용이 되는 전설. 3페이즈에 **붉은 용으로 변신** — 게임의 마지막 보스.

**Style**
```
Grand final boss theme, a legendary carp climbing a moonlit waterfall to transform into a crimson dragon, Korean myth. Starts mysterious with gayageum and daegeum over low drones, then erupts into full orchestra with Korean traditional ensemble, thunderous buk and taiko, epic wordless choir, blazing brass, rapid gayageum runs, climactic key change. 150 BPM, E minor rising to G major, mythic, overwhelming, triumphant, mid-range focused, sparse high end, seamless loop, instrumental.
```
**Exclude** `EDM, pop, lo-fi, rock drum kit, vocals with lyrics`

---

## 4. 보너스 (원하면)

### `title` — 타이틀 화면
**Style**
```
Warm inviting title theme for a challenging but fair pixel-art fishing game, dawn over calm water. Acoustic guitar and gayageum duet, soft strings, gentle glockenspiel, light brushed drums, hopeful melody that hints at adventure. 88 BPM, G major, nostalgic and welcoming, seamless loop, instrumental.
```

### `ending` — 엔딩 (용이 하늘로 오른 뒤, 통계 화면)
**Style**
```
Emotional ending theme after the final legend, a dragon ascending into the moonlit sky over a waterfall. Solo piano and gayageum, slowly joined by strings and soft wordless choir, swelling to a warm bittersweet climax, then calm. 76 BPM, E flat major, grateful, peaceful, a long journey completed, instrumental.
```

---

## 파일 이름 한눈에 보기

```
data/music/
├── spot_reservoir.ogg     fight_reservoir.ogg     legend_golden_carp.ogg
├── spot_valley.ogg        fight_valley.ogg        legend_tiger_mandarin.ogg
├── spot_breakwater.ogg    fight_breakwater.ogg    legend_silver_bass.ogg
├── spot_offshore.ogg      fight_offshore.ogg      legend_marlin.ogg
├── spot_deep.ogg          fight_deep.ogg          legend_coelacanth.ogg
├── spot_secret.ogg        fight_secret.ogg        legend_dragon_carp.ogg
└── title.ogg  ending.ogg  (보너스)
```

> ⚠️ AI 작곡 도구의 저작권·상업 이용 조건은 도구·요금제마다 다르다. 배포(특히 판매) 전에 해당 서비스 약관을 확인할 것.

---

## 5. 엘드라시온 대륙 (확장, 19곡)

샤르미온보다 **신비롭고 마법적인** 음색 (신스 패드·글래스 벨·합창) + 낚시터마다 고유 악기. 파일 이름 규칙은 같다.
엘드라시온 낚시터 id: `marsh` `crystal_cave` `sky_falls` `volcano` `ice_sea` `world_tree`

| 파일 | Style (영어 그대로) |
|---|---|
| `spot_marsh` | `Ethereal silver-reed marsh at dusk with fireflies, gentle fantasy ambient. Soft breathy flute, shimmering glass bells, airy synth pads, slow plucked harp, light rain-stick textures. 70 BPM, A dorian, misty, dreamlike, sparse high end, seamless loop, instrumental.` |
| `fight_marsh` | `Tense fantasy chase through tangled silver reeds. Plucked harp ostinato, low strings staccato, frame drum, flute stabs, swelling choir pad. 138 BPM, A minor, nimble and entangling, mid-range focused, sparse high end, seamless loop, instrumental.` |
| `legend_silva` | `Majestic boss theme for the silver reed king, a giant carp ruling an enchanted marsh. Swirling harp and flute figures, heavy taiko, sweeping strings, wordless female choir, sudden tangled syncopation. 136 BPM, D minor, regal and mysterious, mid-range focused, sparse high end, seamless loop, instrumental.` |
| `spot_crystal_cave` | `Underground crystal lake ambient, glowing crystals in total darkness. Slow celesta and glass harmonica, deep sub drones, water drip percussion with echo, distant choir. 60 BPM, E minor, cavernous reverb, still and glittering, sparse high end, seamless loop, instrumental.` |
| `fight_crystal_cave` | `Dark crystalline battle in a cave, light reflections flickering. Pulsing synth bass, metallic mallet ostinato, echoing tom hits, glass bell accents. 124 BPM, E minor, tense and echoing, low-mid focused, very sparse high end, seamless loop, instrumental.` |
| `legend_prisia` | `Boss theme for the crystal king, a prism fish that shatters light. Cascading celesta and glass arpeggios over heavy orchestral percussion, brass swells, sudden silences when the light goes out. 140 BPM, B minor, dazzling and eerie, mid-range focused, seamless loop, instrumental.` |
| `spot_sky_falls` | `Floating sky islands above a sea of clouds, waterfalls falling into nothing. Soaring strings, light acoustic guitar, airy pan flute, soft wind chimes, gentle percussion. 84 BPM, D major, free and uplifting, wide stereo, sparse high end, seamless loop, instrumental.` |
| `fight_sky_falls` | `Exhilarating aerial chase with rhythmic surges like waves of current. Driving strings in 6/8, pan flute melody, bodhran, swelling brass every four bars. 144 BPM, D mixolydian, breezy and urgent, mid-range focused, sparse high end, seamless loop, instrumental.` |
| `legend_aeris` | `Epic sky boss theme for a winged fish soaring over clouds. Heroic horns, soaring violins, choir, big timpani, wind-like synth sweeps, three-beat leaping motif. 150 BPM, G major to E minor, majestic and airborne, mid-range focused, seamless loop, instrumental.` |
| `spot_volcano` | `Hydrothermal volcanic sea under a red sky, bubbling and smoking. Low didgeridoo-like drones, slow hand drums, distorted cello swells, deep rumbling pads. 72 BPM, C phrygian, hot and heavy, ominous but calm, low-end focused, sparse high end, seamless loop, instrumental.` |
| `fight_volcano` | `Fiery battle against time in boiling water. Driving tribal drums, distorted low brass, aggressive cello ostinato, urgent rising tension every bar. 148 BPM, C phrygian, relentless and scorching, low-mid focused, sparse high end, seamless loop, instrumental.` |
| `legend_ignis` | `Boss theme for a flame shark swimming through magma. Massive taiko and war drums, roaring low brass, distorted guitar undertone, fiery string runs, eruption hits. 156 BPM, F minor, explosive and furious, mid-range focused, seamless loop, instrumental.` |
| `spot_ice_sea` | `Frozen polar sea under shimmering aurora, ice cracking in the distance. Glassy synth pads, slow music box melody, bowed glass, soft low strings. 64 BPM, F sharp minor, cold, vast and beautiful, sparse high end, seamless loop, instrumental.` |
| `fight_ice_sea` | `Tense fight through a narrow ice hole. Icy pizzicato ostinato, low strings, crisp but soft percussion, sharp glass stabs on accents. 132 BPM, F sharp minor, cold and precise, mid-range focused, sparse high end, seamless loop, instrumental.` |
| `legend_borealis` | `Boss theme for the aurora fish dancing beneath the northern lights. Shimmering synth arpeggios, soaring choir, orchestral strings, deep drums, waltz-like swaying sections. 138 BPM, F sharp minor, ethereal and grand, mid-range focused, seamless loop, instrumental.` |
| `spot_world_tree` | `Sacred spring at the roots of a colossal world tree, glowing motes in the air. Harp, kalimba, warm strings, soft choir, gentle wooden flute, nature ambience. 70 BPM, E major, reverent, ancient, healing, sparse high end, seamless loop, instrumental.` |
| `fight_world_tree` | `Mystical battle where the land changes every hour. Shifting orchestration that blends harp, crystal bells, war drums and strings, constant forward pulse. 142 BPM, E minor, majestic and unpredictable, mid-range focused, sparse high end, seamless loop, instrumental.` |
| `legend_orsiel` | `Ultimate final boss theme for the king of sky and sea at the world tree. Four-part structure growing in intensity: tangled harp, dark crystal echoes, soaring sky strings, fire and ice climax. Full orchestra, huge choir, taiko, brass fanfares, key changes. 158 BPM, E minor to E major, overwhelming, mythic, triumphant, seamless loop, instrumental.` |
| `ending_final` | `Emotional final ending after catching the king of sky and sea, aurora over the world tree. Solo piano and harp opening, strings and choir rising to a warm grand climax, then gentle resolution. 74 BPM, E major, grateful, bittersweet, a long journey across two continents complete, instrumental.` |

> `ending_final`이 없으면 최종 엔딩도 `ending` 곡을 쓴다.
