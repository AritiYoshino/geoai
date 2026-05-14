const {createApp, nextTick} = Vue;

async function runStartupTask(taskName, task) {
  try {
    await task();
  } catch (error) {
    console.error(`${taskName} 初始化失败`, error);
    if (taskName === "图层") {
      const layerList = document.getElementById("layerList");
      if (layerList) layerList.innerHTML = '<div class="inline-empty">图层加载失败，请刷新或检查服务日志。</div>';
    }
    if (taskName === "会话") {
      const sessionList = document.getElementById("sessionList");
      if (sessionList) sessionList.innerHTML = '<div class="inline-empty">会话加载失败</div>';
    }
  }
}

createApp({
  data() {
    return {
      sidebarCollapsed: false,
      activeTab: "chat",
      chatInput: "",
      sending: false,
      modulesReady: false,
      gis: {},
      tabs: [
        {id: "chat", label: "对话"},
        {id: "ace", label: "ACE 面板"},
        {id: "trace", label: "ACE 轨迹"},
        {id: "experience", label: "经验库"},
      ],
    };
  },

  async mounted() {
    await nextTick();
    await this.loadGisModules();
    this.initializeMapAndPanels();
  },

  methods: {
    async loadGisModules() {
      const [apiModule, layerModule, mapModule, panelModule] = await Promise.all([
        import("./js/gis/api.js"),
        import("./js/gis/layers.js"),
        import("./js/gis/map_view.js"),
        import("./js/gis/panels.js"),
      ]);
      this.gis = {
        debounce: apiModule.debounce,
        loadLayers: layerModule.loadLayers,
        refreshSelectedLayers: layerModule.refreshSelectedLayers,
        map: mapModule.map,
        clearHighlights: panelModule.clearHighlights,
        createExperienceBank: panelModule.createExperienceBank,
        deleteActiveBank: panelModule.deleteActiveBank,
        newSession: panelModule.newSession,
        refreshAcePanel: panelModule.refreshAcePanel,
        refreshBanks: panelModule.refreshBanks,
        refreshExperience: panelModule.refreshExperience,
        refreshSessions: panelModule.refreshSessions,
        refreshTrace: panelModule.refreshTrace,
        renameActiveBank: panelModule.renameActiveBank,
        sendMessage: panelModule.sendMessage,
        switchExperienceBank: panelModule.switchExperienceBank,
      };
      this.modulesReady = true;
    },

    initializeMapAndPanels() {
      const {map, debounce, refreshSelectedLayers} = this.gis;
      const refreshSelectedLayersDebounced = debounce(() => refreshSelectedLayers(), 450);

      map.on("load", async () => {
        await Promise.all([
          runStartupTask("图层", () => this.gis.loadLayers({fit: true})),
          runStartupTask("会话", this.gis.refreshSessions),
          runStartupTask("ACE 轨迹", this.gis.refreshTrace),
          runStartupTask("ACE 面板", this.gis.refreshAcePanel),
          runStartupTask("经验库摘要", this.gis.refreshExperience),
          runStartupTask("经验库列表", this.gis.refreshBanks),
        ]);
      });

      map.on("moveend", () => {
        refreshSelectedLayersDebounced();
      });
    },

    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed;
      window.setTimeout(() => this.gis.map?.resize(), 260);
    },

    async sendMessage() {
      if (!this.chatInput.trim() || this.sending || !this.modulesReady) return;
      await nextTick();
      this.sending = true;
      try {
        await this.gis.sendMessage();
        this.chatInput = "";
      } finally {
        this.sending = false;
      }
    },

    clearHighlights() {
      return this.gis.clearHighlights?.();
    },

    newSession() {
      return this.gis.newSession?.();
    },

    refreshExperience() {
      return this.gis.refreshExperience?.();
    },

    renameActiveBank() {
      return this.gis.renameActiveBank?.();
    },

    deleteActiveBank() {
      return this.gis.deleteActiveBank?.();
    },

    switchExperienceBank(event) {
      return this.gis.switchExperienceBank?.(event);
    },

    createExperienceBank(template) {
      return this.gis.createExperienceBank?.(template);
    },
  },
}).mount("#gisApp");
