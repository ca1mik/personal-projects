# Reference Schematic v1

## Назначение документа

Это максимально подробный опорный схемный документ для проектирования первой версии оптоволоконной системы связи `точка-точка` на `7-10 км`.

Документ описывает:

- состав узлов
- рекомендуемую структуру принципиальной схемы
- именование основных цепей
- рекомендуемые интерфейсы между узлами
- примерные референс-дизайнаторы
- состав одного оконечного блока

Этот документ можно отдавать инженеру-схемотехнику как исходную основу для переноса в Altium, KiCad, OrCAD или другую EDA-среду.

## Ограничение ответственности

Это не финальный выпускной комплект КД. Для выпуска в производство всё ещё потребуются:

- исходная КД текущего изделия
- подтверждение среды эксплуатации
- подтверждение питания и автономности
- подтверждение требований по взрывозащите, если они обязательны
- полный цикл расчётов, трассировки, DFM и испытаний

## Базовые допущения версии v1

Для того чтобы вообще собрать цельную схему, фиксирую следующие инженерные допущения:

- система состоит из двух одинаковых оконечных блоков `UNIT_A` и `UNIT_B`
- оба блока симметричны по схемотехнике
- связь `точка-точка`
- используется одномодовое волокно
- используется двухволоконная схема `TX` и `RX`
- пользовательская логика остаётся полудуплексной
- передача по волокну цифровая
- питание каждого оконечного блока локальное
- базовое питание схемы проектируется под `VIN = 9..18 VDC`

Если позже подтвердится другой вариант питания, структура схемы в целом не ломается, меняется только узел питания.

## Состав схемы одного оконечного блока

Один блок предлагается делить на такие листы:

1. `SHEET_01_POWER`
2. `SHEET_02_CONTROLLER`
3. `SHEET_03_AUDIO_TX`
4. `SHEET_04_AUDIO_RX`
5. `SHEET_05_OPTICAL_LINK`
6. `SHEET_06_UI_AND_IO`
7. `SHEET_07_SUPERVISION_AND_PROTECTION`

## SHEET_01_POWER

### Назначение

Формирует все внутренние напряжения и обеспечивает защиту питания.

### Предлагаемая структура

```text
J1 VIN_IN+, VIN_IN-
 -> F1 input fuse
 -> D1 TVS surge clamp
 -> Q1 reverse polarity protection
 -> EMI input filter
 -> U1 buck regulator -> +5V_MAIN
 -> U2 LDO -> +3V3_DIG
 -> U3 LDO -> +3V3_ANA
 -> U4 optional boost/audio rail -> +VAMP
```

### Рекомендуемые элементы по классам

- `J1` - входной разъём питания
- `F1` - предохранитель или самовосстанавливающийся PTC
- `D1` - TVS на входе питания
- `Q1` - MOSFET защита от переполюсовки
- `L1/C1/C2` - входной EMI фильтр
- `U1` - понижающий DC/DC для шины `+5V_MAIN`
- `U2` - малошумящий LDO для `+3V3_DIG`
- `U3` - малошумящий LDO для `+3V3_ANA`
- `U4` - отдельный источник для усилителя, если мощности `+5V_MAIN` недостаточно

### Основные сети

- `VIN_RAW`
- `VIN_PROTECTED`
- `+5V_MAIN`
- `+3V3_DIG`
- `+3V3_ANA`
- `+VAMP`
- `GND_PWR`
- `GND_DIG`
- `GND_ANA`

### Обязательные сервисные цепи

- `PWR_GOOD`
- `VBAT_SENSE`
- `LOW_BAT_WARN`
- `LOW_BAT_CUTOFF`

### Что важно в реальной схеме

- аналоговую часть не питать напрямую от шумного DC/DC
- аудиокодек и предусилители вести от отдельной малошумящей шины
- цифровую и аналоговую землю сводить контролируемо
- усилитель громкоговорителя развязывать по питанию отдельно

## SHEET_02_CONTROLLER

### Назначение

Обрабатывает пользовательскую логику, состояние канала, кнопки, индикацию и обмен с транспортом.

### Предлагаемая структура

```text
U10 MCU
  GPIO -> keys, LEDs, buzzer, PTT control
  UART/SPI/I2S -> optical transport / codec
  ADC -> battery measurement
  RESET <- supervisor
  SWD/JTAG -> service header
Y1 crystal or MEMS clock
U11 reset supervisor
J10 debug/programming header
```

### Рекомендуемые референсы

- `U10` - основной контроллер
- `Y1` - тактовый резонатор
- `C10/C11` - обвязка тактирования
- `U11` - supervisor/reset IC
- `R10` - pull-up reset
- `J10` - отладочный разъём
- `R11/R12` - делитель мониторинга питания

### Основные сигналы MCU

#### Входы

- `KEY_CALL_N`
- `KEY_PTT_N`
- `LINK_PRESENT`
- `FAULT_IN`
- `VBAT_ADC`
- `RX_DATA`
- `RX_FRAME_SYNC`
- `AUDIO_ADC_IRQ`

#### Выходы

- `LED_PWR`
- `LED_CALL`
- `LED_TX`
- `LED_FAULT`
- `BUZZER_EN`
- `TX_ENABLE`
- `AMP_EN`
- `CODEC_EN`
- `OPT_TX_EN`
- `TX_DATA`
- `CALL_EVENT_OUT`

### Обязательная логика прошивки

- state machine режимов
- debouncing кнопок
- watchdog recovery
- контроль потери линка
- блокировка одновременной передачи
- оповещение о низком заряде

## SHEET_03_AUDIO_TX

### Назначение

Формирует тракт передачи речи от микрофона до АЦП/кодека.

### Предлагаемая структура

```text
J20 microphone
 -> ESD protection
 -> bias network
 -> U20 low-noise preamp
 -> HPF speech filter
 -> LPF anti-alias filter
 -> gain trim
 -> U21 codec ADC input
```

### Рекомендуемые референсы

- `J20` - разъём микрофона или трубки
- `D20` - ESD защита входа
- `R20/R21/C20` - bias and input network
- `U20A` - предусилитель
- `R22/C21` - HPF
- `R23/C22` - LPF
- `RV20` - подстройка коэффициента усиления, если нужна
- `U21` - аудиокодек

### Основные сети

- `MIC_IN+`
- `MIC_IN-`
- `MIC_BIAS`
- `MIC_PRE_OUT`
- `MIC_FILT_OUT`
- `CODEC_ADC_IN`
- `AUDIO_GND`

### Целевая функция тракта

- речь должна быть разборчивой
- тракт должен быть устойчивым к перегрузке
- должен быть запас по усилению
- уровень микрофона должен регулироваться без перепайки всей схемы

## SHEET_04_AUDIO_RX

### Назначение

Восстанавливает принятый речевой канал и подаёт его на громкоговоритель.

### Предлагаемая структура

```text
U21 codec DAC output
 -> reconstruction filter
 -> volume set network
 -> U30 audio power amplifier
 -> J30 speaker / earpiece
```

### Рекомендуемые референсы

- `U21` - кодек, канал ЦАП
- `R30/C30` - post-DAC filter
- `RV30` - регулировка уровня, если аппаратная
- `U30` - усилитель громкоговорителя
- `J30` - разъём громкоговорителя
- `Z30` - цепь защиты/демпфирования, если нужна

### Основные сети

- `CODEC_DAC_OUT`
- `AUDIO_RX_FILT`
- `AMP_IN`
- `SPK_OUT+`
- `SPK_OUT-`
- `AMP_FAULT`

### Что важно

- усилитель должен уметь работать в шумной среде
- желательно предусмотреть отключение усилителя в ожидании
- при PTT логике нужно исключать паразитную акустическую обратную связь

## SHEET_05_OPTICAL_LINK

### Назначение

Передаёт цифровой поток аудио и служебных команд между двумя блоками.

### Предлагаемая структура

```text
MCU / transport logic
 -> U40 serializer / transport interface
 -> OPT_TX module
 -> J40 TX fiber connector

J41 RX fiber connector
 -> OPT_RX module
 -> U41 receiver / transport interface
 -> MCU / transport logic
```

### Рекомендуемые референсы

- `U40` - передающий интерфейс
- `U41` - принимающий интерфейс
- `J40` - TX optical connector
- `J41` - RX optical connector
- `R40/R41` - bias/termination networks where required
- `U42` - link status conditioning, if needed

### Основные сети

- `TX_DATA`
- `RX_DATA`
- `OPT_TX_EN`
- `LINK_PRESENT`
- `LINK_FAULT`
- `OPT_TX_PWR`
- `OPT_RX_SIG`

### Обязательные свойства

- уверенная работа на расстоянии `10 км` и выше с запасом
- промышленный температурный режим
- сигнал линка для контроллера
- предсказуемое восстановление после обрыва

## SHEET_06_UI_AND_IO

### Назначение

Содержит кнопки, индикацию и местную звуковую сигнализацию.

### Предлагаемая структура

```text
S1 CALL button
S2 PTT button
LED1 PWR
LED2 CALL
LED3 TX
LED4 FAULT
BZ1 buzzer
optional service connector
```

### Рекомендуемые референсы

- `S1` - кнопка вызова
- `S2` - кнопка передачи
- `LED1` - питание
- `LED2` - вызов
- `LED3` - передача
- `LED4` - неисправность
- `R50..R53` - токоограничительные резисторы
- `BZ1` - зуммер
- `Q50` - ключ управления зуммером

### Основные сети

- `KEY_CALL_N`
- `KEY_PTT_N`
- `LED_PWR`
- `LED_CALL`
- `LED_TX`
- `LED_FAULT`
- `BUZZER_EN`

### Примечание

Если заказчик хочет минимум органов управления, достаточно двух кнопок и четырёх индикаторов.

## SHEET_07_SUPERVISION_AND_PROTECTION

### Назначение

Закрывает контроль неисправностей и безопасные состояния.

### Предлагаемая структура

```text
VBAT monitor
watchdog
line/link fault monitor
amp fault monitor
thermal monitor if needed
safe shutdown gating
```

### Рекомендуемые референсы

- `U60` - watchdog or supervisor
- `U61` - battery monitor
- `U62` - fault OR / status conditioning
- `Q60/Q61` - load switches for controlled shutdown

### Основные сети

- `VBAT_ADC`
- `PWR_GOOD`
- `FAULT_IN`
- `AMP_FAULT`
- `LINK_FAULT`
- `SAFE_DISABLE`

## Сводная текстовая схема одного блока

```text
POWER
J1 -> F1 -> D1 -> Q1 -> U1 -> +5V_MAIN
                    -> U2 -> +3V3_DIG
                    -> U3 -> +3V3_ANA
                    -> U4 -> +VAMP

CONTROL
U10 MCU
  <- KEY_CALL_N, KEY_PTT_N, LINK_PRESENT, VBAT_ADC, FAULT_IN
  -> LED_PWR, LED_CALL, LED_TX, LED_FAULT, BUZZER_EN
  -> TX_ENABLE, AMP_EN, OPT_TX_EN
  <-> U21 codec
  <-> U40/U41 transport

AUDIO TX
J20 MIC -> D20 -> U20A -> speech filter -> U21 ADC_IN

AUDIO RX
U21 DAC_OUT -> post filter -> U30 AMP -> J30 SPEAKER

OPTICAL
U10/U21 transport -> U40 -> J40 TX_FIBER
J41 RX_FIBER -> U41 -> U10/U21 transport

SUPERVISION
VBAT_SENSE -> U10 ADC
PWR_GOOD -> U10
AMP_FAULT -> U10
LINK_PRESENT -> U10
```

## Межлистовые интерфейсы

### Power -> Controller

- `+3V3_DIG`
- `GND_DIG`
- `PWR_GOOD`
- `VBAT_ADC`

### Power -> Audio

- `+3V3_ANA`
- `+VAMP`
- `AUDIO_GND`

### Controller -> Audio

- `CODEC_EN`
- `AMP_EN`
- `AUDIO_IF_CLK`
- `AUDIO_IF_DATA`

### Controller -> Optical

- `TX_DATA`
- `RX_DATA`
- `LINK_PRESENT`
- `OPT_TX_EN`

### Controller -> UI

- `LED_*`
- `BUZZER_EN`
- `KEY_*`

## Что должен сделать инженер дальше

После переноса этого документа в EDA инженер должен:

1. Зафиксировать реальное питание.
2. Выбрать конкретный MCU.
3. Выбрать конкретный кодек или вариант без него.
4. Выбрать конкретный оптический транспорт.
5. Уточнить акустический тракт.
6. Добавить расчёт номиналов всех фильтров, делителей и цепей защиты.
7. Проверить EMC, питание, землю и тепловой режим.

## Честный вывод

Это уже не просто “идея”, а реальный reference schematic package уровня pre-design. По нему можно:

- проводить техобсуждение
- оценивать трудоёмкость
- садиться за EDA
- формировать BOM и план макета

Но это ещё не документ уровня “отдал на производство без уточнений”.
