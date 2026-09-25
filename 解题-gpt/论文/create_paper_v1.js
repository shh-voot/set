const {
  AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel, ImageRun, Packer,
  PageBreak, PageNumber, Paragraph, SectionType, ShadingType, Table,
  TableCell, TableRow, TextRun, WidthType
} = require('C:/Users/yoush/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/docx');
const fs = require('fs');
const path = require('path');

const ROOT = 'D:/claude/华为杯/D题/解题-gpt';
const OUT = path.join(ROOT, '论文', '王文政-第一版_符号公式重排版.docx');
// RELATIVE_PATCH_TEST
// TEST_PATCH_APPLIED
const FIG = path.join(ROOT, '可视化', '论文图表');

const colors = { navy: '1F4E79', blue: '5B9BD5', mint: '9CC896', gray: 'F2F5F7', line: 'B7C9D6' };
const fonts = { eastAsia: '宋体', ascii: 'Times New Roman' };
const titleFont = { eastAsia: '黑体', ascii: 'Times New Roman' };

function run(text, opts = {}) {
  return new TextRun({ text, font: fonts, ...opts });
}
function para(text = '', opts = {}) {
  return new Paragraph({
    alignment: opts.alignment || AlignmentType.JUSTIFIED,
    spacing: { after: opts.after ?? 0, line: opts.line ?? 240 },
    indent: opts.indent === false ? undefined : { firstLine: 420 },
    children: [run(text, opts.run || {})],
    ...opts.extra,
  });
}
function richPara(children, opts = {}) {
  return new Paragraph({
    alignment: opts.alignment || AlignmentType.JUSTIFIED,
    spacing: { after: opts.after ?? 0, line: opts.line ?? 240 },
    indent: opts.indent === false ? undefined : { firstLine: 420 },
    children,
  });
}
function heading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({
    text,
    heading: level,
    alignment: level === HeadingLevel.HEADING_1 ? AlignmentType.CENTER : AlignmentType.LEFT,
    spacing: { before: level === HeadingLevel.HEADING_1 ? 240 : 120, after: 80, line: 240 },
    run: { font: titleFont, size: level === HeadingLevel.HEADING_1 ? 28 : 24, bold: true },
    keepNext: true,
  });
}
function bullet(text, level = 0) {
  return new Paragraph({
    text,
    bullet: { level },
    spacing: { after: 0, line: 240 },
    indent: { left: 420 + level * 360, hanging: 240 },
  });
}
function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: 100, line: 240 },
    children: [run(text, { italics: true, color: '666666', size: 20 })],
  });
}
function image(file, width = 650, height = 330) {
  const data = fs.readFileSync(path.join(FIG, file));
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 100, after: 40 },
    children: [new ImageRun({ data, type: 'png', transformation: { width, height } })],
  });
}
function cell(text, opts = {}) {
  return new TableCell({
    width: opts.width ? { size: opts.width, type: WidthType.DXA } : undefined,
    shading: opts.header ? { fill: colors.navy, type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
      spacing: { after: 0, line: 240 },
      children: [run(text, { size: 22, bold: !!opts.header, color: opts.header ? 'FFFFFF' : '222222' })],
    })],
  });
}
function table(headers, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: colors.line },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: colors.line },
      left: { style: BorderStyle.SINGLE, size: 4, color: colors.line },
      right: { style: BorderStyle.SINGLE, size: 4, color: colors.line },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: 'D8E1E8' },
      insideVertical: { style: BorderStyle.SINGLE, size: 2, color: 'D8E1E8' },
    },
    rows: [
      new TableRow({ children: headers.map((h, i) => cell(h, { header: true, width: widths[i], center: true })) }),
      ...rows.map(row => new TableRow({ children: row.map((v, i) => cell(String(v), { width: widths[i] })) })),
    ],
  });
}
function equation(formula, number, explanation) {
  const noBorder = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
  const borders = {
    top: noBorder, bottom: noBorder, left: noBorder, right: noBorder,
    insideHorizontal: noBorder, insideVertical: noBorder,
  };
  const widths = [1350, 6300, 1350];
  const blank = new TableCell({ width: { size: widths[0], type: WidthType.DXA }, children: [new Paragraph('')] });
  const middle = new TableCell({
    width: { size: widths[1], type: WidthType.DXA },
    children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 0, line: 240 }, indent: undefined, children: [run(formula, { font: fonts, size: 23 })] })],
  });
  const right = new TableCell({
    width: { size: widths[2], type: WidthType.DXA },
    children: [new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { after: 0, line: 240 }, indent: undefined, children: [run(number, { font: fonts, size: 22 })] })],
  });
  const block = [new Table({ width: { size: 9000, type: WidthType.DXA }, columnWidths: widths, borders, rows: [new TableRow({ children: [blank, middle, right] })] })];
  if (explanation) block.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 80, line: 240 }, indent: { firstLine: 420 }, children: [run(explanation, { size: 22 })] }));
  return block;
}
function pageBreak() { return new Paragraph({ children: [new PageBreak()] }); }

const children = [];
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 240, after: 120, line: 240 },
  children: [run('“华为杯”第二十三届中国研究生数学建模竞赛', { bold: true, size: 24, color: colors.navy, font: titleFont })],
}));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { after: 260, line: 240 },
  children: [run('山区洪涝灾害下无人机运输与通信协同优化', { bold: true, size: 32, color: '1F1F1F', font: titleFont })],
}));
children.push(heading('摘要', HeadingLevel.HEADING_1));
children.push(para('针对山区洪涝灾害中道路中断、地形起伏、通信盲区和无人机资源受限同时存在的问题，本文以赛题提供的80个货箱、15个服务区、调度中心、A/B/C三类运输无人机、R01/R02两架通信中继、共享电池、通信参数和30 m数字高程模型为唯一数据来源，建立“单架次物理可行性—异构机队调度—通信中继协同—批次资源配置”的四层模型。问题一在每个服务区内进行货箱组批，并使用DEM逐段计算爬升、巡航、下降、返航和作业时间，保证载荷、体积、等效航程、返航能量余量和货箱唯一覆盖约束。问题二采用截止时间优先的任务排序、候选组批、有限宽度束搜索和一交换局部搜索，并通过离散事件仿真处理实体无人机、共享电池和两阶段充电。问题三对调度中心—服务区以及中继—服务区链路进行DEM视距判定和双向链路预算，在官方两架中继数量限制下求解候选位置集合覆盖，并将中继服务窗反馈到运输调度。问题四分别计算各批次独立并行时的资源缺口，再给出允许批次整体错峰复用的补充情景。本文的主要创新是把官方DEM物理可行性、共享电池事件调度和通信中继服务窗放入同一套可核验流程，并明确区分题目规定的独立并行口径与补充的错峰复用情景。'));
children.push(para('当前正式结果为：问题一18架次、按官方3/2次幂等效航程公式复算的总能耗54.1754 kWh；问题二43架次、系统完成时间171.5840 min、总运输能耗93.8540 kWh且80箱全部按时；问题三覆盖15/15服务区、43/43架次通信可用、联合完成时间189.1752 min、运输与中继总能耗99.3546 kWh；问题四独立并行配置存在库存缺口，整体错峰后2批次和3批次分别在274.6992 min和384.0350 min内完成。'));
children.push(richPara([run('关键词：', { bold: true }), run('山区洪涝灾害；无人机运输；异构机队；共享电池；通信中继；资源池化')]));
children.push(pageBreak());

children.push(heading('1 问题重述'));
children.push(para('灾害发生后，调度中心需要向15个服务区配送80个货箱。由于山区高程变化显著，运输无人机不能用平面距离直接替代真实航段；同时，首批保障物资和普通物资具有不同的送达时限，运输无人机和共享电池数量有限。部分服务区到调度中心的通信链路受到地形遮挡，需要部署官方中继无人机保持通信。题目最后要求分析不同任务分区和批次数量对无人机、电池、充电桩及中继能源组件的影响。'));
children.push(para('本文将四个问题分别转化为以下子任务：'));
children.push(bullet('问题一：在单架次往返模式下，完成货箱组批和机型选择，输出每个架次的物理可行性指标。'));
children.push(bullet('问题二：在官方实体机和共享电池库存内，对问题一产生的运输任务进行异构机队调度和时限核验。'));
children.push(bullet('问题三：在官方中继数量和能源组件库存内，完成通信覆盖、中继服务窗和运输任务联合调度。'));
children.push(bullet('问题四：分别给出独立并行执行时的资源缺口，以及整体错峰复用时的库存可行情景。'));

children.push(heading('2 数据、符号与统一计算规则'));
children.push(heading('2.1 官方数据与索引体系', HeadingLevel.HEADING_2));
children.push(para('所有输入数据直接读取D题“数据”目录，包括逐箱货物清单、15个服务区坐标、调度中心坐标、A/B/C三类运输无人机参数、R01/R02中继参数、共享电池参数、通信参数和30 m数字高程模型。官方库存采用A型运输无人机4架、B型2架、C型2架；共享电池为A型6组、B型4组、C型4组；中继无人机为R01和R02各1架，中继能源组件共6组。本文不对官方数据进行补录、平滑或人工替换。为避免在后续章节重复定义，所有公共符号和公共计算规则统一在本章给出。'));
children.push(table(['符号', '含义', '单位'], [
  ['O', '调度中心O01', '—'], ['s∈S', '服务区索引及服务区集合', '—'], ['i∈I', '货箱索引及货箱集合', '—'],
  ['k∈K', '运输无人机型号，K={A,B,C}', '—'], ['m∈M', '运输架次索引及架次集合', '—'], ['r∈R', '中继候选点或中继编号', '—'],
  ['w_i,v_i', '货箱i的质量和体积', 'kg，m³'], ['W_k,V_k', '型号k的最大载质量和最大体积', 'kg，m³'],
  ['q_m', '架次m的有效载荷质量', 'kg'], ['d_s', 'O到服务区s的水平距离', 'm'],
  ['H_s^max,H_s^c', '航段最高地面高程和计划巡航海拔', 'm'], ['L_k(q)', '型号k在载荷q下的等效航程', 'm'],
  ['C_k,ρ_k,E_k^safe', '电池容量、返航余量比例和安全可用能量', 'kWh，—，kWh'],
  ['E_m,T_m', '架次m的往返能耗和总任务时间', 'kWh，min'], ['τ_charge', '电池从返场SOC恢复至目标SOC的充电时间', 'min'],
  ['x_im', '货箱i是否由架次m配送的0-1变量', '—'], ['y_mk', '架次m是否使用型号k的0-1变量', '—'],
  ['a_m,b_m', '架次m的起飞和结束时刻', 'min'], ['z_rs', '中继候选点r是否覆盖服务区s的0-1变量', '—']
], [1900, 5600, 1700]));

children.push(heading('2.2 DEM与运输物理量', HeadingLevel.HEADING_2));
children.push(para('以下公式是四个问题共用的运输物理模型。后续章节只说明新增决策变量和约束，并通过公式编号引用本节结果，不再重复推导。'));
children.push(...equation('d_s=2R_e\\arcsin\\sqrt{\\sin^2((φ_s−φ_O)/2)+\\cos φ_O\\cos φ_s\\sin^2((λ_s−λ_O)/2)}', '(2.1)', '其中R_e为地球平均半径，φ和λ分别为纬度与经度（弧度），下标O和s分别表示调度中心与服务区。'));
children.push(...equation('n_s=\\lceil d_s/Δ_{DEM}\\rceil,\\quad P_{s,j}=O+\\frac{j}{n_s}(S_s−O),\\ j=0,1,…,n_s', '(2.2)', '其中Δ_DEM为DEM采样间隔，P_{s,j}为第j个采样点；该式将整条航段离散为可核验的地形采样点。'));
children.push(...equation('H_s^{max}=\\max_{0≤j≤n_s}H_{DEM}(P_{s,j})', '(2.3)', 'H_DEM(P)表示DEM在地理位置P处的地面高程，H_s^max用于确定该服务区航段的最高地形。'));
children.push(...equation('H_s^c=H_s^{max}+h_{safe}', '(2.4)', 'h_safe为题目规定的安全净空高度；H_s^c为巡航海拔，起飞、巡航、下降阶段均以该高度为基准。'));
children.push(...equation('L_k(q)=L_k^0−(L_k^0−L_k^F)(q/Q_k)^{3/2}', '(2.5)', 'L_k^0和L_k^F分别为型号k空载与满载官方航程，Q_k为最大载质量，q为实际载荷；指数3/2严格采用题面给出的载荷衰减规则。'));
children.push(...equation('T_m=T_{takeoff}+T_{climb}+T_{cruise}+T_{desc}+T_{return}+T_{service}', '(2.6)', 'T_m为架次总任务时间，前五项由航段几何和速度参数计算，T_service为装载、交接等题面规定的作业时间。'));
children.push(...equation('E_m^{cruise}=e_k(q_m)\\,d_s', '(2.7)', 'e_k(q_m)为型号k在载荷q_m下的单位水平航程能耗，d_s为单程水平距离；返航段使用空载参数。'));
children.push(...equation('E_m^{climb}=m_k g\\,Δh_m/(3.6×10^6η_k)', '(2.8)', 'm_k为飞行总质量，Δh_m为净爬升高度，g为重力加速度，η_k为动力系统效率；分母将焦耳转换为kWh。'));
children.push(...equation('E_m^{desc}=\\eta_k^{desc}m_k g\\,Δh_m^{desc}/(3.6×10^6)', '(2.9)', '下降段能耗按官方下降能耗系数η_k^desc计入；若题面将回收能量设为零，则该项按零处理。'));
children.push(...equation('E_m=E_m^{out}(q_m)+E_m^{return}(0)+E_m^{climb}+E_m^{desc}', '(2.10)', 'E_m为架次往返总能耗；出航段载荷为q_m，返航段按空载0计算，能耗由官方参数和DEM高度差共同决定。'));
children.push(...equation('E_k^{safe}=C_k(1−ρ_k),\\quad E_m≤E_k^{safe}', '(2.11)', 'C_k为型号k电池额定容量，ρ_k为返航余量比例；不满足该不等式的架次判为物理不可行。'));
children.push(...equation('t_{ready}=t_{land}+τ_{charge}(SOC_{land},SOC_{target})', '(2.12)', 't_land为返场时刻，SOC_land为返场电量状态，SOC_target为官方目标SOC；该式用于问题二至问题四的共享电池事件调度。'));

children.push(heading('2.3 通信链路与联合可行性', HeadingLevel.HEADING_2));
children.push(...equation('PL_{fs}(D,f)=20\\log_{10}(4πDf/c)', '(2.13)', 'D为链路三维距离，f为载波频率，c为光速；地形遮挡造成的官方障碍损耗在PL_fs基础上叠加。'));
children.push(...equation('M_{rs}^{→}=P_t+G_t+G_r−PL_{rs}^{→}−P_{min},\\quad M_{rs}^{←}≥M_{min}', '(2.14)', 'M_rs^→和M_rs^←分别为正向、反向链路裕度，P_t为发射功率，G_t/G_r为天线增益，P_min为接收灵敏度，M_min为官方安全裕度。'));
children.push(...equation('z_{rs}=1\\iff LOS_{rs}=1\\land M_{rs}^{→}≥M_{min}\\land M_{rs}^{←}≥M_{min}', '(2.15)', 'LOS_rs为DEM视距判定结果。只有视距、正向裕度和反向裕度同时通过，候选中继r才可为服务区s提供通信。'));

children.push(heading('2.4 基本假设与约束口径', HeadingLevel.HEADING_2));
children.push(bullet('每个货箱只能配送一次；每个运输架次从调度中心出发并按官方任务模型返航。'));
children.push(bullet('载荷、体积、航程和能量约束统一使用式(2.5)–式(2.11)计算，DEM高程不以平面距离或截图数值替代。'));
children.push(bullet('运输无人机与共享电池按机型分组，任务开始时同时占用一架实体无人机和一组同型电池，任务结束后按式(2.12)回池。'));
children.push(bullet('问题四同时报告题目要求的独立并行口径和补充的整体错峰复用口径，后者不替代前者。'));

children.push(heading('3 问题一：单架次物理可行性与货箱组批'));
children.push(heading('3.1 问题一局部符号与目标', HeadingLevel.HEADING_2));
children.push(table(['本章符号', '含义', '说明'], [
  ['B_s', '服务区s的货箱集合', '由官方货箱清单按服务区划分'],
  ['B_s', '服务区s的货箱集合', '由官方货箱清单按服务区划分'],
  ['G_{s,u}', '服务区s的第u个货箱组', '一个运输架次对应一个组'],
  ['N_s', '服务区s的架次数', '目标是最小化Σ_s N_s'],
  ['R_{s,u}', '第u组的物理可行性标志', '载荷、体积、航程和能量均通过时为1'],
  ['R_{s,u}', '第u组的物理可行性标志', '载荷、体积、航程、能量均通过时为1']
], [2200, 4700, 2300]));
children.push(para('问题一只研究单架次往返下的货箱组批和机型选择，不引入实体无人机并行、共享电池排队或中继服务窗约束。距离、高程、等效航程、时间、能耗和安全余量均直接调用第二章式(2.1)–式(2.12)。'));

children.push(para('对于每个服务区，先按截止时间优先、质量降序、体积降序构造货箱序列，再使用First-Fit Decreasing逐个放入已有货箱组。向组G_{s,u}加入货箱i前，检查质量和体积约束，并调用式(2.5)至式(2.11)重新计算等效航程、往返能耗和返航余量；任一条件不满足则拒绝该放置。如果所有已有组均不满足，则建立新架次。'));
children.push(para('初始组批完成后执行局部移动：将一个架次中的货箱尝试移动到另一架次，仅当架次数不增加、两架次均满足式(2.5)至式(2.11)，且总能耗不升高时才接受。该过程只改变组批顺序，不改变官方货箱属性、服务区归属和DEM输入。'));
children.push(para('对于每个服务区，先按“截止时间优先、质量降序、体积降序”的稳定规则构造货箱序列，再使用First-Fit Decreasing逐个放入已有货箱组。向组G_{s,u}加入货箱i前，检查质量和体积约束，并调用式(2.5)–式(2.11)重新计算等效航程、往返能耗和返航余量；任一条件不满足则拒绝该放置。如果所有已有组均不满足，则建立新架次。'));
children.push(para('初始组批完成后执行局部移动：将一个架次中的货箱尝试移动到另一架次，仅当架次数不增加、两架次均满足式(2.5)–式(2.11)，且总能耗不升高时才接受。该过程只改变组批顺序，不改变官方货箱属性、服务区归属和DEM输入。距离、高程、时间和能耗均由第二章统一公式计算。'));
children.push(para('对于每个服务区，先按“截止时间优先、质量降序、体积降序”的稳定规则构造货箱序列，再使用First-Fit Decreasing逐个放入已有货箱组。向组G_{s,u}加入货箱i前，检查Σ_{i∈G_{s,u}}w_i≤W_k、Σ_{i∈G_{s,u}}v_i≤V_k，并调用式(2.5)–式(2.11)重新计算等效航程、往返能耗和安全余量；任一条件不满足则拒绝该放置。如果所有已有组均不满足，则建立新架次。初始组批完成后执行局部移动：把一个架次中的货箱尝试移动到另一架次，仅当架次数不增加、两架次均满足式(2.5)–式(2.11)，且总能耗不升高时才接受。该过程只改变组批顺序，不改变官方货箱属性和DEM输入。'));
children.push(para('架次数的理论下界由服务区不可跨区约束给出：对每个服务区s，先以型号k的最大安全载荷和最大体积计算该服务区的质量下界、体积下界，再取两者上界并求和。本文最终解达到18架次，且每个服务区的组批均通过逐架次物理核验。'));
children.push(image('问题一_路径与约束指标.png', 650, 315));
children.push(caption('图1  官方DEM底图上的问题一运输路径与物理约束指标'));
children.push(heading('3.3 结果与核验', HeadingLevel.HEADING_2));
children.push(table(['指标', '正式结果', '核验说明'], [
  ['运输架次', '18', '覆盖80箱且货箱编号无重复'],
  ['总能耗', '54.1754 kWh', '按式(2.5)–式(2.11)复算，18个架次均满足返航安全能量约束'],
  ['架次任务时间总和', '550.0312 min', '问题一无实体机并行调度约束'],
  ['最长单架次时间', '38.6048 min', '包含飞行、装载、交接等官方作业时间'],
  ['物理可行性', '100%', '载荷、体积、DEM、航程和能量余量均通过']
], [2600, 2300, 4300]));

children.push(pageBreak());
children.push(heading('4 问题二：异构机队与共享电池调度'));
children.push(heading('4.1 本章新增符号', HeadingLevel.HEADING_2));
children.push(table(['符号', '含义', '在本章中的作用'], [
  ['N_late', '迟到货箱数', '首要评价指标，要求为0'],
  ['Δ_late', '货箱总迟到时间', '在迟到箱数相同时比较'],
  ['C_max', '系统最大完成时刻', '衡量实体机和电池调度效率'],
  ['A_k(t),B_k(t)', '时刻t可用的实体机数和电池数', '用于事件驱动资源核验'],
  ['τ_m', '架次m的开始时刻', '由同型无人机和电池可用时刻共同决定']
], [1800, 4200, 4000]));
children.push(heading('4.2 候选组批与机型选择', HeadingLevel.HEADING_2));
children.push(para('问题二不重新估计货箱需求，而是读取官方货箱清单和问题一产生的可行货箱组，按服务区及官方截止时间形成任务序列。对每个任务组分别生成A/B/C机型候选方案，记录架次数、任务时长、能耗和逐箱送达时间。机型选择采用截止时间优先（EDD）与机队稀缺性反馈：相同截止时间下优先保障紧急货箱，在机型选择时同时考虑完成波次、任务时长、能耗和可用实体机数量。'));
children.push(para('问题二不重新估计货箱需求，而是读取官方货箱清单和DEM任务模型，按服务区及官方截止时间形成任务组。对每个任务组分别生成A/B/C机型候选组批，记录架次数、任务时长、能耗和逐箱送达时间。机型选择采用截止时间优先（EDD）和机队稀缺性反馈：在相同截止时间下优先保障紧急系数较高的货箱，在机型选择时综合考虑完成波次、任务时长、能耗和可用实体机数量。该处理与时间窗路径问题中区分车辆异质性和时间窗可行性的思想一致[6]。'));
children.push(heading('4.3 有限宽度搜索与局部改进', HeadingLevel.HEADING_2));
children.push(para('将任务组的机型选择视为序列决策。束搜索每一步保留若干具有不同机型组合的候选状态，状态评价按迟到箱数、总迟到时间、系统完成时间、总能耗和架次数的词典序最小化。搜索结束后执行一交换局部搜索：若替换一个架次的机型能够改善评价函数，且重新调用第二章物理核验后仍可行，则接受替换。'));
children.push(para('将每个任务组的机型选择视为序列决策。束搜索每一步保留一组具有不同机型组合的候选状态，状态评价采用词典序：迟到箱数、总迟到时间、系统完成时间、总能耗和架次数。束搜索结束后，针对单个任务组进行一交换局部搜索，若替换机型能够改善评价函数且仍满足官方物理约束，则接受该替换。所有候选架次均重新调用问题一的DEM任务函数，避免使用平面距离或经验能耗。'));
children.push(richPara([run('候选状态评价：', { bold: true }), run('Lex(S)=(N_late,\u00a0\u0394_late,\u00a0C_max,\u00a0E_total,\u00a0N_trip)，按字典序最小化；其中N_late为迟到货箱数，\u0394_late为总迟到时间，C_max为系统完成时间，E_total为总能耗，N_trip为架次数。该多目标优先级借鉴多架次完成时间和异构车辆路径的分层评价思路[3][6][7]。')], { indent: false }));
children.push(heading('4.4 电池离散事件仿真', HeadingLevel.HEADING_2));
children.push(para('任务开始时刻取同型实体无人机与共享电池可用时刻的最大值。任务结束后实体机立即释放；电池根据返场SOC和式（2.12）计算充电完成时刻，再返回共享池。事件队列按“任务结束、充电完成、任务开始”更新，因此同时表达实体机并发限制、电池数量限制和充电占用限制。'));
children.push(para('任务开始时间取同型实体无人机和共享电池可用时间的最大值。任务结束后，实体无人机立即释放；电池按照任务结束时SOC和官方两阶段充电函数计算充电完成时间，再回到共享池。这样可以同时表达实体机并发限制、电池数量限制和充电占用限制。电池调度采用事件驱动更新：若架次m在时刻t_m结束、SOC为s_m，则其下一次可用时刻为t_m+\u03c4_charge(s_m,1)，并要求任意任务开始时刻均有一组同型电池可用。这与无缺货充电调度文献中“返回时刻—电池身份—充电完成时刻”联动的建模方式相符[4]。'));
children.push(image('问题二_性能与资源峰值.png', 650, 350));
children.push(caption('图2  问题二正式方案的性能指标、实体机峰值与时限核验'));
children.push(heading('4.5 结果与核验', HeadingLevel.HEADING_2));
children.push(table(['指标', '正式结果', '说明'], [
  ['运输架次', '43', '所有架次来自官方DEM可行候选组批'],
  ['系统完成时间', '171.5840 min', '实体机和共享电池离散事件调度后的最大返回时间'],
  ['总运输能耗', '93.8540 kWh', '逐架次官方能耗之和'],
  ['按时货箱', '80/80', '逐箱交付时间均不超过官方截止时间'],
  ['迟到货箱', '0', '总迟到时间为0'],
  ['资源核验', '通过', 'A/B/C实体机和共享电池未超过4/2/2、6/4/4']
], [2600, 2300, 4300]));

children.push(heading('5 问题三：运输与通信中继协同'));
children.push(heading('5.1 本章新增符号', HeadingLevel.HEADING_2));
children.push(table(['符号', '含义', '在本章中的作用'], [
  ['u_r', '候选中继位置r是否被选用', '受两架官方中继数量约束'],
  ['LOS_rs', '候选中继r到服务区s的DEM视距结果', '判定地形是否遮挡'],
  ['M_rs^→,M_rs^←', '正向和反向链路裕度', '要求双向同时达到安全阈值'],
  ['W_r', '中继r的通信服务窗', '运输架次必须在服务窗内保持链路'],
  ['E_r^relay', '中继飞行和悬停能耗', '纳入联合能耗评价']
], [2200, 4300, 3500]));
children.push(heading('5.2 双向链路预算', HeadingLevel.HEADING_2));
children.push(para('对调度中心—服务区和中继—服务区链路沿完整路径采样。每个采样点使用DEM进行地形视距判定；若射线被地形遮挡，则加入官方障碍损耗。链路同时计算正向和反向接收功率，并调用式（2.13）至式（2.15）要求两个方向的链路裕度均达到安全阈值。'));
children.push(para('对调度中心—服务区和中继—服务区链路沿完整路径采样。每个采样点使用DEM进行地形视距判定；若射线被地形遮挡，则加入官方障碍损耗。链路同时计算正向和反向接收功率，并要求两个方向的链路裕度均达到官方安全裕度。该处理避免只检查端点或只检查单向链路造成的虚假覆盖。对候选中继位置r和服务区s，定义双向链路可行变量z_rs；只有正向、反向链路裕度和DEM视距均通过时才令z_rs=1。三维位置与链路能耗同时进入候选评价，参考了山区通信中继位置优化对覆盖与能源权衡的处理[5]。'));
children.push(heading('5.3 两中继集合覆盖', HeadingLevel.HEADING_2));
children.push(para('在服务区经纬度范围内建立候选中继网格，计算每个候选位置的覆盖集合、飞行能耗、悬停能耗和能源组件需求。由于官方只提供R01和R02两架中继，枚举候选位置对并最大化覆盖服务区数量；覆盖数量相同时优先选择能源组件少、服务开始时间早、能耗低的组合。对每个服务区s要求Σ_r u_r z_rs≥1，并要求Σ_r u_r≤2。'));
children.push(para('在服务区经纬度范围内建立候选中继网格，计算每个候选位置对非直连服务区的覆盖集合、飞行能耗、悬停能耗和能源组件需求。由于官方只提供R01和R02两架中继，枚举候选位置对并最大化覆盖服务区数量；在覆盖数量相同的情况下，优先选择能源组件少、服务开始时间早、能耗低的组合。集合覆盖约束写为：对每个服务区s，\u03a3_r x_r z_rs≥1；对中继数量，\u03a3_r x_r≤2；其中x_r表示候选位置是否选用。由于候选点数量有限，本文采用全枚举而不是将启发式覆盖率当作证明。'));
children.push(heading('5.4 联合时间调度', HeadingLevel.HEADING_2));
children.push(para('中继任务包括准备、单程飞行、建链、悬停服务和返航。根据中继服务窗重新检查运输任务：直连区域可直接执行，依赖中继的任务必须在对应服务窗内完成通信。之后重新按截止时间进行运输调度，并再次核验逐箱时限、通信可用性和中继能源组件数量。'));
children.push(para('中继任务包括准备、单程飞行、建链、悬停服务和返航。根据中继服务窗重新检查运输任务：直连区域可直接执行；依赖中继的任务必须在对应中继服务窗内完成通信。之后重新按截止时间进行运输调度，并再次检查逐箱时限、通信可用性和中继能源组件数量。'));
children.push(image('问题三_通信覆盖与中继窗口.png', 650, 325));
children.push(caption('图3  官方DEM视距判定下的中继覆盖与服务窗口'));
children.push(table(['指标', '正式结果'], [
  ['服务区覆盖', '15/15，覆盖率100%'], ['运输通信', '43/43架次可用'], ['运输任务完成', '180.3517 min'],
  ['联合完成时间', '189.1752 min'], ['运输与中继总能耗', '99.3546 kWh'], ['中继能源组件', '4/6组']
], [4200, 5000]));

children.push(pageBreak());
children.push(heading('6 问题四：批次资源配置与错峰复用'));
children.push(heading('6.1 本章新增符号', HeadingLevel.HEADING_2));
children.push(table(['符号', '含义', '在本章中的作用'], [
  ['g', '批次编号', '用于区分独立并行任务组'],
  ['r', '资源类型', '运输无人机、电池、充电桩或中继能源组件'],
  ['q_gr', '批次g对资源r的峰值需求', '独立并行情景下统计'],
  ['I_r', '官方资源r库存', '来自题目官方数据'],
  ['G_gr', '资源缺口max(0,q_gr−I_r)', '判断独立并行是否可行']
], [1800, 4700, 3500]));
children.push(heading('6.2 独立并行口径', HeadingLevel.HEADING_2));
children.push(para('题目要求不同任务组独立执行时，组间资源不得调配。因此，将所有批次同时置于时间轴上，对每一组统计运输无人机、电池、充电桩和中继能源组件峰值，再与官方库存逐项比较。对资源类型r和批次g，记峰值需求为q_gr、官方库存为I_r，则独立并行缺口为G_gr=max(0,q_gr−I_r)。只有所有G_gr=0时，独立并行配置才可行；缺口不以虚构资源填补。'));
children.push(para('题目要求不同任务组独立执行时，组间资源不得调配。因此，先把所有批次同时置于时间轴上，对每一组在自身任务窗口内统计运输无人机、电池、充电桩和中继能源组件峰值，再与官方库存逐项比较。对资源类型r和批次g，记峰值需求为q_gr、官方库存为I_r，则独立并行缺口为G_gr=max(0,q_gr−I_r)，只有所有G_gr=0时才称为库存内可行。该口径用于判断仅依靠官方资源是否可行，缺口必须如实报告。'));
children.push(table(['批次数', '资源', '需求', '官方库存', '缺口'], [
  ['2批次', '运输无人机 A/B/C', '6/3/4', '4/2/2', '2/1/2'],
  ['2批次', '共享电池 A/B/C', '8/5/6', '6/4/4', '2/1/2'],
  ['3批次', '运输无人机 A/B/C', '7/4/5', '4/2/2', '3/2/3'],
  ['3批次', '共享电池 A/B/C', '9/5/7', '6/4/4', '3/1/3'],
  ['2/3批次', '中继能源组件', '4', '6', '0']
], [1600, 2700, 1800, 1800, 1300]));
children.push(heading('6.3 错峰复用补充情景', HeadingLevel.HEADING_2));
children.push(para('在不增加官方资源的前提下，保持每个批次内部任务的相对时刻不变，令批次之间不重叠，使同一架无人机和电池可以在不同批次之间复用。该结果只作为资源池化和时间复用的补充情景，不替代独立并行缺口结论。'));
children.push(para('在不增加官方资源的前提下，将每个批次内部任务相对时间关系保持不变，令批次之间不重叠，使同一架无人机和电池可以在不同批次之间复用。该结果是对资源池化和时间复用的情景分析，不替代独立并行结论，也不意味着题目中的独立执行约束被放宽。错峰目标可表示为在批次内部相对时刻不变的条件下最小化总完成时间C_max；这属于资源复用情景，而非对独立并行约束的重新解释。'));
children.push(image('问题四_资源池化与错峰复用.png', 650, 320));
children.push(caption('图4  独立并行资源缺口与整体错峰复用情景'));
children.push(table(['情景', '完成时间', '运输无人机', '共享电池', '官方库存可行'], [
  ['2批次整体错峰', '274.6992 min', 'A/B/C=4/2/2', 'A/B/C=6/4/4', '是'],
  ['3批次整体错峰', '384.0350 min', 'A/B/C=4/2/2', 'A/B/C=6/3/4', '是']
], [2600, 1900, 1900, 1900, 1300]));

children.push(heading('7 模型验证与结果讨论'));
children.push(heading('7.1 约束验证', HeadingLevel.HEADING_2));
children.push(bullet('货箱唯一性：运输结果以官方80箱编号为键检查，未发现重复配送或漏配送。'));
children.push(bullet('物理可行性：每架次均检查载荷、体积、DEM最高地面高程、等效航程和返航能量余量。'));
children.push(bullet('时限约束：问题二和问题三逐箱核验送达时间，正式结果迟到箱数为0。'));
children.push(bullet('通信约束：问题三同时核验15个服务区覆盖、43/43架次通信可用和中继能源组件4/6组。'));
children.push(bullet('库存约束：问题四区分独立并行缺口和错峰复用，不用虚构资源填补缺口。'));
children.push(bullet('货箱唯一性：四问运输结果均以官方80箱编号为键检查，未发现重复配送或漏配送。'));
children.push(bullet('物理可行性：每一架次均检查载荷、体积、DEM最高地面高程、等效航程和返航能量余量。'));
children.push(bullet('时限约束：问题二和问题三均逐箱核验送达时间，正式结果迟到箱数为0。'));
children.push(bullet('通信约束：问题三同时核验15个服务区覆盖、43个运输架次通信可用和中继能源组件4/6组。'));
children.push(bullet('库存约束：问题四明确区分独立并行缺口和错峰复用情景，未用虚构资源填补缺口。'));
children.push(heading('7.2 与截图参考方案的可比性', HeadingLevel.HEADING_2));
children.push(para('问题一与参考截图均为18架次，具有有限可比性；本文正式结果按官方3/2次幂等效航程公式复算。问题二至问题四的截图未提供逐架次路径、逐箱送达时刻、SOC、充电记录、中继服务窗和分组峰值定义，因此截图数字只作为外部参考，不能替换官方数据结果。'));
children.push(para('问题一与参考截图均为18架次，具有有限可比性：本文总能耗56.5159 kWh，截图显示59.1323 kWh，但两边的时间汇总和具体载荷顺序尚未完全统一。问题二至问题四的截图未提供逐架次路径、逐箱送达时刻、SOC、充电记录、中继服务窗和分组峰值定义；同时截图方案可能允许多服务区串联。因此，截图数字仅作为外部参考，不能替换官方数据结果，也不能在缺少约束证据时直接进行算法排名。'));

children.push(heading('8 结论与局限'));
children.push(para('本文基于官方数据完成四个问题的统一建模和可复核求解。问题一给出18架次的单架次物理可行方案；问题二在官方异构机队和共享电池库存下完成43架次运输并实现80箱零迟到；问题三使用两架官方中继完成15个服务区覆盖和43/43架次通信可用；问题四明确报告独立并行资源缺口，并给出整体错峰复用后的库存可行情景。'));
children.push(para('上述结果是满足硬约束的可行解，不宣称四个问题的全局最优。后续优化必须保持官方DEM、能耗、通信、时限和库存约束不变，再扩展多服务区路径候选和批次联合搜索。'));
children.push(para('本文基于官方数据完成了四个问题的统一建模和可复核求解。问题一给出18架次的单架次物理可行方案；问题二在官方异构机队和共享电池库存下完成43架次运输并实现80箱零迟到；问题三使用两架官方中继完成15个服务区覆盖和43/43架次通信可用；问题四证明独立并行配置存在资源缺口，同时给出整体错峰复用后的官方库存可行情景。'));
children.push(para('本文当前方案是满足硬约束的可行解，不宣称四个问题的全局最优。问题二和问题三的当前候选路径以服务区单点完整任务为主，尚未将所有跨服务区串联路线纳入统一搜索；问题四的错峰复用结果也不等价于独立并行要求。后续若继续优化，应保持官方DEM、能耗、通信、时限和库存约束不变，再扩展多服务区路径候选和批次联合搜索。'));

children.push(heading('参考文献'));
const refs = [
  'K. Chen, Y. Suo, S. Cui, et al., Trajectory Optimization for UAV-Based Medical Delivery with Temporal Logic Constraints and Convex Feasible Set Collision Avoidance, arXiv:2506.06038, 2025.',
  'T. I. Faiz, C. Vogiatzis, and M. Noor-E-Alam, A Robust Optimization Framework for Two-Echelon Vehicle and UAV Routing for Post-Disaster Humanitarian Logistics Operations, arXiv:2207.11879, 2022.',
  'T. Calamoneri, F. Corò, and S. Mancini, Multi-Depot Multi-Trip Vehicle Routing with Total Completion Time Minimization, arXiv:2207.06155, 2022.',
  'E. Cho, J. Cho, H. Lee, et al., Scalable No-Stockout Charging Scheduling for Battery Swapping Under Time-of-Use Prices, arXiv:2607.23922, 2026.',
  'H. Liu, M. S. Bashir, and M.-S. Alouini, 3-D Position Optimization of Solar-Powered Hovering UAV Relay in Optical Wireless Backhaul, arXiv:2401.16601, 2024.',
  'A. Abu-Monshar and A. Al-Bazi, A multi-objective centralised agent-based optimisation approach for vehicle routing problem with unique vehicles, Applied Soft Computing, 125:109187, 2022.',
  'N. A. Wouda, L. Lan, and W. Kool, PyVRP: a high-performance VRP solver package, arXiv:2403.13795, 2024.',
];
refs.forEach((x, i) => children.push(new Paragraph({ text: `[${i + 1}] ${x}`, spacing: { after: 80, line: 300 }, indent: { left: 420, hanging: 420 } })));

const doc = new Document({
  creator: '数学建模竞赛论文第一版',
  title: '山区洪涝灾害下无人机运输与通信协同优化',
  description: '基于官方数据的第一版论文草稿',
  styles: {
    default: { document: { run: { font: fonts, size: 24 }, paragraph: { spacing: { line: 240, after: 0 } } } },
    title: { run: { font: titleFont, size: 32, bold: true } },
    heading1: { run: { font: titleFont, size: 28, bold: true, color: '000000' }, paragraph: { outlineLevel: 0, alignment: AlignmentType.CENTER, spacing: { line: 240, before: 240, after: 80 } } },
    heading2: { run: { font: titleFont, size: 24, bold: true, color: '000000' }, paragraph: { outlineLevel: 1, alignment: AlignmentType.LEFT, spacing: { line: 240, before: 120, after: 80 } } },
  },
  sections: [{
    properties: {
      page: { margin: { top: 1640, right: 1000, bottom: 400, left: 1160, header: 0, footer: 0 }, size: { width: 11906, height: 16840 } },
      type: SectionType.CONTINUOUS,
    },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 0, line: 240 }, children: [new TextRun({ children: [PageNumber.CURRENT], font: fonts, size: 24 })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buffer => fs.writeFileSync(OUT, buffer));
