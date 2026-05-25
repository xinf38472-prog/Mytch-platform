const STUDENT_ATTRS = [
  { key: "gpa", label: "学历与成绩", min: 0, max: 4 },
  { key: "internship", label: "实习/项目", min: 0, max: 5 },
  { key: "skills", label: "技能/证书", min: 0, max: 5 },
  { key: "personality", label: "个性特质", min: 0, max: 1 },
  { key: "soft", label: "软技能", min: 0, max: 1 }
];

const DEMO_STORAGE_KEY = "mytchDemoPayload:v2-full-seed";

const STUDENT_PROFILE_FIELDS = [
  {
    key: "schoolText",
    label: "学校",
    placeholder: "例如：上海财经大学 / University of Manchester"
  },
  {
    key: "gpaText",
    label: "GPA / 绩点",
    placeholder: "例如：GPA 3.6/4.0，或均分 88/100。"
  },
  {
    key: "majorText",
    label: "专业",
    placeholder: "例如：Data Science、Business Analytics、软件工程。"
  },
  {
    key: "courseText",
    label: "相关课程",
    placeholder: "例如：Statistics、Python、Database、Machine Learning、市场研究。"
  },
  {
    key: "internshipText",
    label: "实习 / 项目经历",
    placeholder: "例如：腾讯产品运营实习 3 个月，参与用户增长数据分析项目；也可写课程项目、竞赛项目。"
  },
  {
    key: "skillsText",
    label: "技能与证书",
    placeholder: "例如：Python, SQL, Excel, Tableau, CET-6，有数据分析证书和机器学习项目。"
  },
  {
    key: "personalityText",
    label: "个性特质描述",
    placeholder: "例如：责任心强，抗压能力较好，目标感强，适应速度快。"
  },
  {
    key: "softText",
    label: "软技能经历",
    placeholder: "例如：曾担任小组项目 leader，负责沟通协调和 final presentation。"
  }
];

const COMPANY_ATTRS = [
  { key: "salary", label: "薪资回报", min: 3000, max: 15000 },
  { key: "location", label: "地点/远程", min: 0, max: 1 },
  { key: "career", label: "成长机会", min: 0, max: 1 },
  { key: "reputation", label: "公司声誉", min: 0, max: 1 },
  { key: "meaning", label: "岗位匹配", min: 0, max: 1 }
];

const COMPANY_PROFILE_FIELDS = [
  {
    key: "salaryText",
    label: "薪资与福利描述",
    placeholder: "例如：月薪 12k-18k，13 薪，餐补交通补贴，绩效奖金。"
  },
  {
    key: "locationText",
    label: "办公地点 / 远程方式",
    placeholder: "例如：上海核心商圈，混合办公；或远程友好、偶尔出差。"
  },
  {
    key: "careerText",
    label: "成长机会描述",
    placeholder: "例如：导师制、轮岗、完善培训、清晰晋升路径、参与核心项目。"
  },
  {
    key: "reputationText",
    label: "公司声誉描述",
    placeholder: "例如：头部互联网平台、行业领先品牌、稳定上市公司、早期创业团队。"
  },
  {
    key: "meaningText",
    label: "岗位内容与匹配描述",
    placeholder: "例如：数据分析岗位，服务增长业务，强调 SQL/Python、用户研究和业务洞察。"
  }
];

const STUDENT_PREFS = [
  { key: "salary", label: "薪资" },
  { key: "location", label: "地点" },
  { key: "career", label: "成长机会" },
  { key: "reputation", label: "公司声誉" },
  { key: "meaning", label: "岗位匹配度" }
];

const COMPANY_PREFS = [
  { key: "gpa", label: "学历与成绩" },
  { key: "skills", label: "技能证书" },
  { key: "internship", label: "实习项目" },
  { key: "personality", label: "个性特质" },
  { key: "soft", label: "软技能" }
];

const stateStore = {
  payload: null,
  selectedStudentId: "",
  selectedCompanyId: "",
  matrixMode: "student"
};

const $ = (selector) => document.querySelector(selector);
const page = document.body?.dataset.page;

function html(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[char]);
}

function byId(items = []) {
  return Object.fromEntries(items.map((item) => [item.id, item]));
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, Number(value) || 0));
}

function toDisplayScore(value, attr) {
  const normalized = (Number(value) - attr.min) / (attr.max - attr.min || 1);
  return Math.round(clamp(normalized * 10, 0, 10) * 10) / 10;
}

function fromDisplayScore(value, attr) {
  const normalized = clamp(Number(value), 0, 10) / 10;
  return Math.round((attr.min + normalized * (attr.max - attr.min)) * 1000) / 1000;
}

function pct(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function score(value) {
  return Number(value || 0).toFixed(3);
}

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, item) => sum + Number(item || 0), 0) / values.length;
}

function hasText(value) {
  return String(value || "").trim().length > 0;
}

function profileHasAny(profile, keys) {
  return keys.some((key) => hasText(profile[key]));
}

function hasStudentEvidence(profile) {
  return profileHasAny(profile, STUDENT_PROFILE_FIELDS.map((field) => field.key));
}

function hasStudentPreference(profile) {
  return hasText(profile.preferenceText);
}

function hasCompanyEvidence(profile) {
  return profileHasAny(profile, COMPANY_PROFILE_FIELDS.map((field) => field.key));
}

function hasCompanyPreference(profile) {
  return hasText(profile.candidateText);
}

function pendingInference(title, message) {
  return `
    <div class="pending-state">
      <strong>${html(title)}</strong>
      <span>${html(message)}</span>
    </div>
  `;
}

function splitEducationText(text) {
  const source = String(text || "");
  const gpa = source.match(/(?:GPA|绩点)?\s*(\d+(?:\.\d+)?)\s*\/\s*4(?:\.0)?/i);
  const major = source.match(/[，,]\s*([^，,。；;]+?)\s*专业/);
  const courses = source.match(/相关课程(?:包括|有)?\s*([^。；;]+)/);
  return {
    gpaText: gpa ? `GPA ${gpa[1]}/4.0` : "",
    majorText: major ? major[1].trim() : "",
    courseText: courses ? courses[1].replace(/^[：:，,\s]+|[。；;\s]+$/g, "") : ""
  };
}

function defaultSalaryText(value) {
  const salary = Math.round(Number(value) || 0);
  if (!salary) return "";
  if (salary >= 1000) return `月薪约 ${Math.round(salary / 1000)}k，具体福利以企业公示为准。`;
  return `薪资约 ${salary} 元，具体福利以企业公示为准。`;
}

function profileFieldValue(profile, field, entity = {}) {
  if (hasText(profile[field.key])) return profile[field.key];
  if (field.key === "gpaText" || field.key === "majorText" || field.key === "courseText") {
    return splitEducationText(profile.educationText)[field.key];
  }
  if (field.key === "salaryText") {
    return defaultSalaryText(entity.salary);
  }
  return "";
}

async function loadPayload() {
  try {
    const response = await fetch("/api/state");
    if (!response.ok) throw new Error(`接口返回 ${response.status}`);
    stateStore.payload = await response.json();
    stateStore.demoMode = false;
    const demoResponse = await fetch(`demo_state.json?v=${Date.now()}`, { cache: "no-store" });
    if (demoResponse.ok) {
      const demoPayload = await demoResponse.json();
      const apiSize = (stateStore.payload.state?.students?.length || 0) + (stateStore.payload.state?.companies?.length || 0);
      const demoSize = (demoPayload.state?.students?.length || 0) + (demoPayload.state?.companies?.length || 0);
      if (demoSize > apiSize) {
        stateStore.payload = demoPayload;
        stateStore.demoMode = true;
      }
    }
  } catch (error) {
    const stored = localStorage.getItem(DEMO_STORAGE_KEY);
    if (stored) {
      stateStore.payload = JSON.parse(stored);
    } else {
      const demoResponse = await fetch("demo_state.json");
      if (!demoResponse.ok) throw error;
      stateStore.payload = await demoResponse.json();
    }
    stateStore.demoMode = true;
  }
  return stateStore.payload;
}

async function savePayload(messageTarget) {
  if (stateStore.demoMode) {
    localStorage.setItem(DEMO_STORAGE_KEY, JSON.stringify(stateStore.payload));
    setStateText(messageTarget, "演示模式：已暂存在当前浏览器，GitHub Pages 不连接 MySQL");
    renderCurrentPage();
    return;
  }
  setStateText(messageTarget, "正在保存到 MySQL...");
  const response = await fetch("/api/state", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state: stateStore.payload.state })
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `保存失败 ${response.status}`);
  }
  stateStore.payload = await response.json();
  setStateText(messageTarget, "已保存并重新匹配");
  renderCurrentPage();
}

function setStateText(selector, text) {
  const node = $(selector);
  if (node) node.textContent = text;
}

function optionLabel(item) {
  return `${item.id}: ${item.name || item.id}`;
}

function sortHumanFirst(items) {
  return [...items].sort((a, b) => {
    const aAi = String(a.id || "").startsWith("AI") ? 1 : 0;
    const bAi = String(b.id || "").startsWith("AI") ? 1 : 0;
    return aAi - bAi || String(a.id).localeCompare(String(b.id), "zh-CN", { numeric: true });
  });
}

function firstHuman(items) {
  return sortHumanFirst(items)[0];
}

function fillSelect(selector, items, selectedId) {
  const select = $(selector);
  if (!select) return;
  const sortedItems = sortHumanFirst(items);
  select.innerHTML = sortedItems.map((item) => `<option value="${html(item.id)}">${html(optionLabel(item))}</option>`).join("");
  select.value = selectedId || sortedItems[0]?.id || "";
}

function getStudent() {
  const students = stateStore.payload?.state.students || [];
  return students.find((item) => item.id === stateStore.selectedStudentId) || firstHuman(students);
}

function getCompany() {
  const companies = stateStore.payload?.state.companies || [];
  return companies.find((item) => item.id === stateStore.selectedCompanyId) || firstHuman(companies);
}

function renderCurrentPage() {
  if (page === "student") renderStudentPage();
  if (page === "company") renderCompanyPage();
  if (page === "admin") renderAdminPage();
}

function renderStudentPage() {
  const { state } = stateStore.payload;
  const student = getStudent();
  if (!student) return;
  stateStore.selectedStudentId = student.id;

  fillSelect("#studentSelect", state.students, student.id);
  $("#studentOverviewId").textContent = student.id;
  $("#studentUpdatedAt").textContent = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });

  const profile = state.studentProfiles[student.id] || {};
  const weights = state.studentWeights[student.id] || {};
  $("#studentWeightStatus").textContent = hasStudentPreference(profile) ? "已生成" : "待填写";
  renderStudentForm(student, profile);
  renderStudentPreferenceForm(weights, profile);
  if (hasStudentEvidence(profile)) {
    renderRadar("#studentRadarChart", STUDENT_ATTRS.map((attr) => ({ label: attr.label, value: toDisplayScore(student[attr.key], attr) })));
  } else {
    $("#studentRadarChart").innerHTML = pendingInference("等待生成能力图", "填写学校、GPA、专业、课程和经历后，系统会自动生成五维能力评分。");
  }
  renderWeightBars("#studentWeightFields", STUDENT_PREFS, hasStudentPreference(profile) ? weights : null);
  renderStudentRanking(student.id);
  renderStudentResult(student.id);
}

function renderStudentForm(student, profile) {
  $("#studentIdentityFields").innerHTML = `
    <label class="text-field"><span>学生ID</span><input name="id" value="${html(student.id)}" readonly /></label>
    <label class="text-field"><span>学生名称</span><input name="name" value="${html(student.name || student.id)}" /></label>
  `;

  const inferredCards = STUDENT_ATTRS.map((attr) => `
    <article class="sim-card">
      <span>${html(attr.label.replace("评分", ""))}</span>
      <strong>${toDisplayScore(student[attr.key], attr)}/10</strong>
    </article>
  `).join("");

  const profileFields = STUDENT_PROFILE_FIELDS.map((field) => `
    <label class="text-field">
      <span>${html(field.label)}</span>
      <textarea name="${html(field.key)}" placeholder="${html(field.placeholder)}">${html(profileFieldValue(profile, field, student))}</textarea>
    </label>
  `).join("");

  const inference = hasStudentEvidence(profile) ? `
    <div class="inference-card generated-card">
      <strong>系统自动生成的五维能力评分</strong>
      <p>学生只提交学校、GPA、专业、课程和经历描述；保存后，后端会根据规则自动计算下方分数，并写入 MySQL。</p>
      <div class="simulation-results">${inferredCards}</div>
    </div>
  ` : pendingInference("尚未生成能力评分", "请先填写上方个人资料与经历描述，系统会在保存后生成数字结果。");

  $("#studentAttrFields").innerHTML = `${profileFields}${inference}`;
}

function renderStudentPreferenceForm(weights, profile) {
  const preview = hasStudentPreference(profile) ? `
    <div class="inference-card generated-card">
      <strong>系统自动生成的求职偏好权重</strong>
      <p>权重由求职偏好描述自动推断，并在保存后标准化为匹配算法可用的比例。</p>
      ${renderWeightPreview(STUDENT_PREFS, weights)}
    </div>
  ` : pendingInference("尚未生成求职权重", "请用自然语言描述你更看重薪资、地点、成长、声誉还是岗位匹配度。");

  $("#studentPreferenceFields").innerHTML = `
    <label class="text-field">
      <span>求职偏好描述</span>
      <textarea name="preferenceText" placeholder="例如：我希望优先考虑成长机会和岗位内容，其次是薪资；地点最好在上海或支持远程。">${html(profile.preferenceText || "")}</textarea>
    </label>
    ${preview}
  `;
}

function renderCompanyPage() {
  const { state } = stateStore.payload;
  const company = getCompany();
  if (!company) return;
  stateStore.selectedCompanyId = company.id;

  fillSelect("#companySelect", state.companies, company.id);
  $("#companyOverviewId").textContent = company.id;
  $("#companyUpdatedAt").textContent = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });

  const profile = state.companyProfiles[company.id] || {};
  const weights = state.companyWeights[company.id] || {};
  renderCompanyForm(company, profile);
  renderCompanyPreferenceForm(weights, profile);
  if (hasCompanyEvidence(profile)) {
    renderBarChart("#companyBarChart", COMPANY_ATTRS.map((attr) => ({ label: attr.label, value: toDisplayScore(company[attr.key], attr) })));
  } else {
    $("#companyBarChart").innerHTML = pendingInference("等待生成岗位属性图", "填写薪资、地点、成长、声誉和岗位内容后，系统会自动生成企业五维属性。");
  }
  if (hasCompanyPreference(profile)) {
    renderDonut("#companyDonutChart", COMPANY_PREFS.map((pref) => ({ label: pref.label, value: Number(weights[pref.key]) || 0 })));
  } else {
    $("#companyDonutChart").innerHTML = pendingInference("等待生成招聘权重", "填写候选人偏好描述后，系统会自动生成企业评价候选人的权重。");
  }
  renderCompanyRanking(company.id);
  renderCompanyResult(company.id);
}

function renderCompanyForm(company, profile) {
  $("#companyIdentityFields").innerHTML = `
    <label class="text-field"><span>企业ID</span><input name="id" value="${html(company.id)}" readonly /></label>
    <label class="text-field"><span>企业名称</span><input name="name" value="${html(company.name || company.id)}" /></label>
  `;

  const profileFields = COMPANY_PROFILE_FIELDS.map((field) => `
    <label class="text-field">
      <span>${html(field.label)}</span>
      <textarea name="${html(field.key)}" placeholder="${html(field.placeholder)}">${html(profileFieldValue(profile, field, company))}</textarea>
    </label>
  `).join("");

  const inferredCards = COMPANY_ATTRS.map((attr) => `
    <article class="sim-card">
      <span>${html(attr.label)}</span>
      <strong>${toDisplayScore(company[attr.key], attr)}/10</strong>
    </article>
  `).join("");

  const inference = hasCompanyEvidence(profile) ? `
    <div class="inference-card generated-card">
      <strong>系统自动生成的企业五维属性</strong>
      <p>企业只填写岗位与雇主描述；系统保存后自动推断薪资、地点、成长、声誉和岗位匹配度评分。</p>
      <div class="simulation-results">${inferredCards}</div>
    </div>
  ` : pendingInference("尚未生成企业属性评分", "请先填写上方岗位与企业描述，系统会在保存后生成数字结果。");

  $("#companyAttrFields").innerHTML = `${profileFields}${inference}`;
}

function renderCompanyPreferenceForm(weights, profile) {
  const preview = hasCompanyPreference(profile) ? `
    <div class="inference-card generated-card">
      <strong>系统自动生成的人才评价权重</strong>
      <p>权重由企业候选人偏好描述自动推断，并用于生成候选人排序。</p>
      ${renderWeightPreview(COMPANY_PREFS, weights)}
    </div>
  ` : pendingInference("尚未生成招聘权重", "请描述企业更看重学历成绩、技能证书、实习项目、个性特质还是软技能。");

  $("#companyPreferenceFields").innerHTML = `
    <label class="text-field">
      <span>候选人偏好描述</span>
      <textarea name="candidateText" placeholder="例如：更看重 Python/SQL 技能和真实项目经验，同时希望候选人沟通清楚、稳定负责。">${html(profile.candidateText || "")}</textarea>
    </label>
    ${preview}
  `;
}

function renderWeightPreview(prefs, weights) {
  return `
    <div class="weight-preview">
      ${prefs.map((pref) => {
        const value = Number(weights?.[pref.key]) || 0;
        return `<div><span>${html(pref.label)}</span><b>${pct(value)}</b><em><i style="width:${Math.round(value * 100)}%"></i></em></div>`;
      }).join("")}
    </div>
  `;
}

function renderWeightBars(selector, prefs, weights) {
  const target = $(selector);
  if (!target) return;
  if (!weights) {
    target.innerHTML = pendingInference("等待生成权重图", "保存求职偏好描述后，这里会展示系统生成的权重比例。");
    return;
  }
  target.innerHTML = prefs.map((pref) => {
    const value = Number(weights[pref.key]) || 0;
    return `
      <div class="bar-row">
        <div class="bar-label"><span>${html(pref.label)}</span><strong>${pct(value)}</strong></div>
        <div class="bar-track"><span style="width:${Math.round(value * 100)}%"></span></div>
      </div>
    `;
  }).join("");
}

function renderRadar(selector, items) {
  const size = 260;
  const center = size / 2;
  const radius = 88;
  const points = items.map((item, index) => {
    const angle = -Math.PI / 2 + (Math.PI * 2 * index) / items.length;
    const valueRadius = radius * clamp(item.value, 0, 10) / 10;
    return {
      ...item,
      x: center + Math.cos(angle) * valueRadius,
      y: center + Math.sin(angle) * valueRadius,
      lx: center + Math.cos(angle) * (radius + 30),
      ly: center + Math.sin(angle) * (radius + 30),
      ax: center + Math.cos(angle) * radius,
      ay: center + Math.sin(angle) * radius
    };
  });
  $(selector).innerHTML = `
    <svg viewBox="0 0 ${size} ${size}" role="img" aria-label="五维能力雷达图">
      ${[2, 4, 6, 8, 10].map((level) => {
        const ringPoints = points.map((p, index) => {
          const angle = -Math.PI / 2 + (Math.PI * 2 * index) / points.length;
          const ringRadius = radius * level / 10;
          return `${center + Math.cos(angle) * ringRadius},${center + Math.sin(angle) * ringRadius}`;
        }).join(" ");
        return `<polygon points="${ringPoints}" fill="${level === 10 ? 'rgba(15,118,110,.035)' : 'none'}" stroke="#b9d8d4" stroke-width="${level === 10 ? 1.5 : 1}" />`;
      }).join("")}
      ${points.map((p) => `<line x1="${center}" y1="${center}" x2="${p.ax}" y2="${p.ay}" stroke="#b9d8d4" stroke-width="1.2" />`).join("")}
      <polygon points="${points.map((p) => `${p.x},${p.y}`).join(" ")}" fill="rgba(0,183,163,.20)" stroke="#1b4ed8" stroke-width="4" stroke-linejoin="round" />
      ${points.map((p) => `<circle cx="${p.x}" cy="${p.y}" r="4.5" fill="#00b7a3" stroke="#ffffff" stroke-width="2" />`).join("")}
      ${points.map((p) => `<text x="${p.lx}" y="${p.ly}" text-anchor="middle" dominant-baseline="middle" font-size="12" font-weight="800" fill="#0d1b2a">${html(p.label)}</text>`).join("")}
    </svg>
  `;
}

function renderBarChart(selector, items) {
  $(selector).innerHTML = items.map((item) => `
    <div class="bar-row">
      <div class="bar-label"><span>${html(item.label)}</span><strong>${item.value}/10</strong></div>
      <div class="bar-track"><span style="width:${item.value * 10}%"></span></div>
    </div>
  `).join("");
}

function renderDonut(selector, items) {
  const rawTotal = items.reduce((sum, item) => sum + Number(item.value || 0), 0);
  const normalizedItems = rawTotal > 0
    ? items.map((item) => ({ ...item, value: Number(item.value || 0) / rawTotal }))
    : items.map((item) => ({ ...item, value: 1 / items.length }));
  let offset = 0;
  const colors = ["#008f7c", "#1b4ed8", "#00b7a3", "#f47b20", "#8b5cf6"];
  const circles = normalizedItems.map((item, index) => {
    const dash = Math.max(0.5, item.value * 100);
    const circle = `<circle class="donut-segment" r="34" cx="50" cy="50" fill="transparent" stroke="${colors[index]}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${dash} ${100 - dash}" stroke-dashoffset="${-offset}" />`;
    offset += item.value * 100;
    return circle;
  }).join("");
  const topItem = normalizedItems.reduce((best, item) => item.value > best.value ? item : best, normalizedItems[0]);
  $(selector).innerHTML = `
    <div class="donut-visual">
      <svg viewBox="0 0 100 100" aria-label="招聘权重比例图">
        <defs>
          <filter id="donutShadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="#0d1b2a" flood-opacity=".12"/>
          </filter>
        </defs>
        <circle r="34" cx="50" cy="50" fill="transparent" stroke="#e8eff4" stroke-width="12" />
        <g transform="rotate(-90 50 50)">${circles}</g>
        <circle r="22" cx="50" cy="50" fill="#ffffff" filter="url(#donutShadow)" />
      </svg>
      <span><strong>${pct(topItem.value)}</strong><em>最高权重</em></span>
    </div>
    <div class="donut-legend">
      ${normalizedItems.map((item, index) => `<span><i style="background:${colors[index]}"></i>${html(item.label)} ${pct(item.value)}</span>`).join("")}
    </div>
  `;
}

function renderStudentRanking(studentId) {
  const { state, result } = stateStore.payload;
  const companies = byId(state.companies);
  const prefs = result.prefs?.studentPrefs?.[studentId] || [];
  $("#studentPersonalPrefs").innerHTML = prefs.map((companyId, index) => `
    <article>
      <strong>${index + 1}. ${html(companies[companyId]?.name || companyId)}</strong>
      <span>${html(companyId)} · 学生效用 ${score(result.studentUtilities?.[studentId]?.[companyId])}</span>
    </article>
  `).join("");
}

function renderCompanyRanking(companyId) {
  const { state, result } = stateStore.payload;
  const students = byId(state.students);
  const prefs = result.prefs?.companyPrefs?.[companyId] || [];
  $("#companyPersonalPrefs").innerHTML = prefs.map((studentId, index) => `
    <article>
      <strong>${index + 1}. ${html(students[studentId]?.name || studentId)}</strong>
      <span>${html(studentId)} · 企业效用 ${score(result.companyUtilities?.[companyId]?.[studentId])}</span>
    </article>
  `).join("");
}

function findCompanyForStudent(studentId) {
  const held = stateStore.payload.result.heldByCompany || {};
  return Object.keys(held).find((companyId) => held[companyId] === studentId);
}

function renderStudentResult(studentId) {
  const { state, result } = stateStore.payload;
  const companies = byId(state.companies);
  const companyId = findCompanyForStudent(studentId);
  const company = companies[companyId] || {};
  const blockingCount = (result.blockingPairs || []).length;
  $("#studentStableBadge").textContent = blockingCount ? "Unstable" : "Stable";
  $("#studentResult").innerHTML = companyId ? `
    <div class="result-main">
      <span class="result-kicker">${html(studentId)}</span>
      <strong>${html(company.name || companyId)}</strong>
      <span>第 ${(result.prefs.studentPrefs[studentId] || []).indexOf(companyId) + 1} 志愿 · V=${score(result.studentUtilities[studentId][companyId])} · U=${score(result.companyUtilities[companyId][studentId])}</span>
    </div>
    <div class="match-card">
      <article><span>成功匹配率</span><strong>${pct(result.metrics.successRate)}</strong></article>
      <article><span>阻塞对</span><strong>${blockingCount}</strong></article>
    </div>
  ` : `<p class="empty-state">当前学生暂未匹配到企业。</p>`;
}

function renderCompanyResult(companyId) {
  const { state, result } = stateStore.payload;
  const students = byId(state.students);
  const studentId = result.heldByCompany?.[companyId];
  const student = students[studentId] || {};
  const blockingCount = (result.blockingPairs || []).length;
  $("#companyStableBadge").textContent = blockingCount ? "Unstable" : "Stable";
  $("#companyResult").innerHTML = studentId ? `
    <div class="result-main">
      <span class="result-kicker">${html(companyId)}</span>
      <strong>${html(student.name || studentId)}</strong>
      <span>企业偏好第 ${(result.prefs.companyPrefs[companyId] || []).indexOf(studentId) + 1} 位 · V=${score(result.companyUtilities[companyId][studentId])} · U=${score(result.studentUtilities[studentId][companyId])}</span>
    </div>
    <div class="match-card">
      <article><span>成功匹配率</span><strong>${pct(result.metrics.successRate)}</strong></article>
      <article><span>阻塞对</span><strong>${blockingCount}</strong></article>
    </div>
  ` : `<p class="empty-state">当前企业暂未匹配到学生。</p>`;
}

function updateStudentFromForm() {
  const student = getStudent();
  const state = stateStore.payload.state;
  const values = new FormData($("#studentForm"));
  const prefValues = new FormData();
  $("#studentPreferenceFields").querySelectorAll("input, textarea").forEach((input) => prefValues.set(input.name, input.value));

  student.name = values.get("name") || student.name;
  state.studentProfiles[student.id] = state.studentProfiles[student.id] || {};
  STUDENT_PROFILE_FIELDS.forEach((field) => {
    state.studentProfiles[student.id][field.key] = values.get(field.key) || "";
  });
  state.studentProfiles[student.id].preferenceText = prefValues.get("preferenceText") || "";

  setStateText("#studentState", "已提交资料，系统正在生成能力评分与求职权重...");
}

function updateCompanyFromForm() {
  const company = getCompany();
  const state = stateStore.payload.state;
  const values = new FormData($("#companyForm"));
  const prefValues = new FormData();
  $("#companyPreferenceFields").querySelectorAll("input, textarea").forEach((input) => prefValues.set(input.name, input.value));

  company.name = values.get("name") || company.name;
  state.companyProfiles[company.id] = state.companyProfiles[company.id] || {};
  COMPANY_PROFILE_FIELDS.forEach((field) => {
    state.companyProfiles[company.id][field.key] = values.get(field.key) || "";
  });
  state.companyProfiles[company.id].candidateText = prefValues.get("candidateText") || "";
  setStateText("#companyState", "已提交企业资料，系统正在生成岗位属性与招聘权重...");
}

function addStudent() {
  const state = stateStore.payload.state;
  const index = state.students.length + 1;
  const id = `Student_New_${String(index).padStart(2, "0")}`;
  state.students.push({ id, name: id, gpa: 2.0, internship: 0.5, skills: 1.0, personality: 0.5, soft: 0.45 });
  state.studentWeights[id] = { salary: 0.2, location: 0.2, career: 0.2, reputation: 0.2, meaning: 0.2 };
  state.studentProfiles[id] = { schoolText: "", gpaText: "", majorText: "", courseText: "", educationText: "", internshipText: "", skillsText: "", personalityText: "", softText: "", preferenceText: "" };
  stateStore.selectedStudentId = id;
  savePayload("#studentState").catch(showError);
}

function addCompany() {
  const state = stateStore.payload.state;
  const index = state.companies.length + 1;
  const id = `Company_New_${String(index).padStart(2, "0")}`;
  state.companies.push({ id, name: id, salary: 9000, location: 0.5, career: 0.5, reputation: 0.5, meaning: 0.5 });
  state.companyWeights[id] = { gpa: 0.2, skills: 0.2, internship: 0.2, personality: 0.2, soft: 0.2 };
  state.companyProfiles[id] = { salaryText: "", locationText: "", careerText: "", reputationText: "", meaningText: "", candidateText: "" };
  stateStore.selectedCompanyId = id;
  savePayload("#companyState").catch(showError);
}

function renderAdminPage() {
  const { state, result, database } = stateStore.payload;
  $("#studentCount").textContent = state.students.length;
  $("#companyCount").textContent = state.companies.length;
  $("#matchedCount").textContent = Object.keys(result.heldByCompany || {}).length;
  $("#blockingPairCount").textContent = (result.blockingPairs || []).length;
  $("#avgUtility").textContent = score((result.metrics.studentAvg + result.metrics.companyAvg) / 2);
  $("#studentAvg").textContent = score(result.metrics.studentAvg);
  $("#companyAvg").textContent = score(result.metrics.companyAvg);
  $("#totalUtility").textContent = score(result.metrics.totalUtility);
  $("#studentAvgBar").style.width = `${Math.round(result.metrics.studentAvg * 100)}%`;
  $("#companyAvgBar").style.width = `${Math.round(result.metrics.companyAvg * 100)}%`;
  $("#totalUtilityBar").style.width = `${Math.min(100, Math.round(result.metrics.totalUtility * 10))}%`;
  $("#successRate").textContent = pct(result.metrics.successRate);
  $("#stableBadge").textContent = (result.blockingPairs || []).length ? "Unstable" : "Stable";
  $("#sidebarState").textContent = database?.startsWith("mysql://") ? "MySQL 数据已同步" : "后台数据已同步";
  $("#adminConsoleLog").innerHTML = [
    `已连接数据库：${database || "-"}`,
    `加载学生 ${state.students.length} 个，企业 ${state.companies.length} 个。`,
    `GS 算法完成 ${result.rounds.length} 轮，阻塞对 ${(result.blockingPairs || []).length} 个。`
  ].map((line) => `<p>${html(line)}</p>`).join("");

  renderMatchCards();
  renderMatrix();
  renderAdminTables();
  renderAdminPreferences();
  renderRounds();
  renderAiCards();
  renderAudit();
}

function renderMatchCards() {
  const { state, result } = stateStore.payload;
  const students = byId(state.students);
  const companies = byId(state.companies);
  $("#matchCards").innerHTML = Object.entries(result.heldByCompany || {}).map(([companyId, studentId]) => `
    <article class="match-card">
      <strong>${html(students[studentId]?.name || studentId)} → ${html(companies[companyId]?.name || companyId)}</strong>
      <span>学生效用 ${score(result.studentUtilities[studentId][companyId])} · 企业效用 ${score(result.companyUtilities[companyId][studentId])}</span>
    </article>
  `).join("");
}

function renderMatrix() {
  const { state, result } = stateStore.payload;
  const isStudent = stateStore.matrixMode === "student";
  const rows = isStudent ? state.students : state.companies;
  const cols = isStudent ? state.companies : state.students;
  const utilities = isStudent ? result.studentUtilities : result.companyUtilities;
  $("#utilityMatrix").innerHTML = `
    <table>
      <thead><tr><th>${isStudent ? "学生/企业" : "企业/学生"}</th>${cols.map((item) => `<th>${html(item.id)}</th>`).join("")}</tr></thead>
      <tbody>${rows.map((row) => `<tr><th>${html(row.id)}</th>${cols.map((col) => `<td>${score(utilities[row.id]?.[col.id])}</td>`).join("")}</tr>`).join("")}</tbody>
    </table>
  `;
}

function renderTable(selector, headers, rows) {
  $(selector).innerHTML = `
    <thead><tr>${headers.map((item) => `<th>${html(item)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((row) => `<tr>${row.map((item) => `<td>${html(item)}</td>`).join("")}</tr>`).join("")}</tbody>
  `;
}

function renderAdminTables() {
  const { state } = stateStore.payload;
  renderTable("#studentTable", ["ID", "名称", "学历", "实习", "技能", "个性", "软技能"], state.students.map((s) => [
    s.id, s.name, ...STUDENT_ATTRS.map((attr) => toDisplayScore(s[attr.key], attr))
  ]));
  renderTable("#companyTable", ["ID", "名称", "薪资", "地点", "成长", "声誉", "匹配"], state.companies.map((c) => [
    c.id, c.name, ...COMPANY_ATTRS.map((attr) => toDisplayScore(c[attr.key], attr))
  ]));
  renderTable("#studentWeightTable", ["学生ID", ...STUDENT_PREFS.map((p) => p.label)], state.students.map((s) => [
    s.id, ...STUDENT_PREFS.map((p) => pct(state.studentWeights[s.id]?.[p.key] || 0))
  ]));
  renderTable("#companyWeightTable", ["企业ID", ...COMPANY_PREFS.map((p) => p.label)], state.companies.map((c) => [
    c.id, ...COMPANY_PREFS.map((p) => pct(state.companyWeights[c.id]?.[p.key] || 0))
  ]));
}

function renderAdminPreferences() {
  const { state, result } = stateStore.payload;
  $("#studentPreferences").innerHTML = state.students.map((s) => `<article><strong>${html(s.id)}</strong><span>${(result.prefs.studentPrefs[s.id] || []).join(" > ")}</span></article>`).join("");
  $("#companyPreferences").innerHTML = state.companies.map((c) => `<article><strong>${html(c.id)}</strong><span>${(result.prefs.companyPrefs[c.id] || []).join(" > ")}</span></article>`).join("");
}

function renderRounds() {
  const rounds = stateStore.payload.result.rounds || [];
  $("#roundCount").textContent = `${rounds.length} rounds`;
  $("#roundTimeline").innerHTML = rounds.map((round) => `
    <details class="timeline-item">
      <summary>第 ${round.number} 轮：${Object.keys(round.proposals || {}).length} 家企业收到申请</summary>
      <pre>${html(JSON.stringify(round, null, 2))}</pre>
    </details>
  `).join("");
}

function renderAiCards() {
  const { state } = stateStore.payload;
  const aiItems = [...state.students, ...state.companies].filter((item) => String(item.id).startsWith("AI"));
  $("#aiMarketCards").innerHTML = aiItems.map((item) => `<article><strong>${html(item.id)}</strong><span>${html(item.name || item.id)}</span></article>`).join("");
}

function renderAudit() {
  const { state } = stateStore.payload;
  const rows = [...state.students.slice(0, 8), ...state.companies.slice(0, 8)].map((item) => {
    const trust = String(item.id).startsWith("AI") ? 0.82 : 0.76;
    return [item.id, item.name, pct(0.15 + (1 - trust) * 0.6), Math.round(1000 + (1 - trust) * 5000)];
  });
  $("#truthAuditTable").innerHTML = `<table><thead><tr><th>主体</th><th>名称</th><th>审计概率</th><th>保证金</th></tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${html(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

function runSimulation() {
  const students = Number($("#simStudents").value) || 200;
  const companies = Number($("#simCompanies").value) || 50;
  const capacity = Number($("#simCapacity").value) || 4;
  const matched = Math.min(students, companies * capacity);
  $("#simulationResults").innerHTML = `
    <article><strong>${matched}</strong><span>模拟可容纳匹配人数</span></article>
    <article><strong>${Math.round(matched / students * 100)}%</strong><span>估算匹配覆盖率</span></article>
    <article><strong>${Math.round(Math.log2(students * companies) * 10) / 10}</strong><span>相对计算规模指数</span></article>
  `;
}

function setupEvents() {
  $("#studentSelect")?.addEventListener("change", (event) => {
    stateStore.selectedStudentId = event.target.value;
    renderStudentPage();
  });
  $("#companySelect")?.addEventListener("change", (event) => {
    stateStore.selectedCompanyId = event.target.value;
    renderCompanyPage();
  });
  $("#studentForm")?.addEventListener("submit", (event) => {
    event.preventDefault();
    updateStudentFromForm();
    savePayload("#studentState").catch(showError);
  });
  $("#companyForm")?.addEventListener("submit", (event) => {
    event.preventDefault();
    updateCompanyFromForm();
    savePayload("#companyState").catch(showError);
  });
  $("#newStudentBtn")?.addEventListener("click", addStudent);
  $("#newCompanyBtn")?.addEventListener("click", addCompany);
  $("#runBtn")?.addEventListener("click", () => loadPayload().then(renderAdminPage).catch(showError));
  $("#loadExampleBtn")?.addEventListener("click", async () => {
    if (stateStore.demoMode) {
      localStorage.removeItem(DEMO_STORAGE_KEY);
      const demoResponse = await fetch("demo_state.json");
      stateStore.payload = await demoResponse.json();
      renderAdminPage();
      return;
    }
    const response = await fetch("/api/reset", { method: "POST" });
    if (!response.ok) throw new Error("恢复示例数据失败");
    stateStore.payload = await response.json();
    renderAdminPage();
  });
  $("#runSimulationBtn")?.addEventListener("click", runSimulation);
  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-tab]").forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === button.dataset.tab));
      $("#pageTitle").textContent = button.textContent.replace(/^\d+/, "").trim();
    });
  });
  document.querySelectorAll("[data-matrix]").forEach((button) => {
    button.addEventListener("click", () => {
      stateStore.matrixMode = button.dataset.matrix;
      document.querySelectorAll("[data-matrix]").forEach((item) => item.classList.toggle("active", item === button));
      renderMatrix();
    });
  });
}

function showError(error) {
  console.error(error);
  const message = `数据加载失败：${error.message || error}`;
  setStateText("#studentState", message);
  setStateText("#companyState", message);
  const log = $("#adminConsoleLog");
  if (log) log.innerHTML = `<p>${html(message)}</p>`;
}

async function boot() {
  if (!["student", "company", "admin"].includes(page)) return;
  setupEvents();
  await loadPayload();
  stateStore.selectedStudentId = firstHuman(stateStore.payload.state.students)?.id || "";
  stateStore.selectedCompanyId = firstHuman(stateStore.payload.state.companies)?.id || "";
  renderCurrentPage();
}

boot().catch(showError);
