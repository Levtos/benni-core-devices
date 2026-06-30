const DOMAIN = "benni_core_devices";

export class Store {
  constructor() {
    this.hass = null;
    this.status = null;
    this.catalog = null;
    this.contractCatalog = null;
    this.rawEntityCatalog = null;
  }

  _ws(msg) {
    if (!this.hass) return Promise.reject(new Error("no hass"));
    return this.hass.connection.sendMessagePromise(msg);
  }

  async refresh() {
    const [status, catalog] = await Promise.all([
      this._ws({ type: `${DOMAIN}/get_status` }).catch((e) => ({ _error: String(e.message || e) })),
      this.catalog ? Promise.resolve(this.catalog) : this._ws({ type: `${DOMAIN}/get_catalog` }),
    ]);
    this.status = status;
    this.catalog = catalog;
    return this;
  }

  async getContractCatalog() {
    const result = await this._ws({ type: `${DOMAIN}/get_contract_catalog` });
    this.contractCatalog = result;
    return result;
  }

  async getRawEntityCatalog(filters = {}) {
    const payload = { type: `${DOMAIN}/get_raw_entity_catalog` };
    if (filters.domain) payload.domain = filters.domain;
    if (filters.search) payload.search = filters.search;
    if (filters.only_available) payload.only_available = true;
    const result = await this._ws(payload);
    this.rawEntityCatalog = result;
    return result;
  }

  async setDevice(payload) {
    const result = await this._ws({ type: `${DOMAIN}/set_device`, ...payload });
    await this.refresh();
    return result;
  }

  async removeDevice(slug) {
    const result = await this._ws({ type: `${DOMAIN}/remove_device`, slug });
    await this.refresh();
    return result;
  }

  async setGroup(payload) {
    const result = await this._ws({ type: `${DOMAIN}/set_group`, ...payload });
    await this.refresh();
    return result;
  }

  async removeGroup(slug) {
    const result = await this._ws({ type: `${DOMAIN}/remove_group`, slug });
    await this.refresh();
    return result;
  }

  async bulkImport(payload, dryRun = false) {
    const result = await this._ws({
      type: `${DOMAIN}/bulk_import`,
      payload,
      dry_run: dryRun,
    });
    if (!dryRun) await this.refresh();
    return result;
  }

  async setCombined(payload) {
    const result = await this._ws({ type: `${DOMAIN}/set_combined`, ...payload });
    await this.refresh();
    return result;
  }

  async removeCombined(slug) {
    const result = await this._ws({ type: `${DOMAIN}/remove_combined`, slug });
    await this.refresh();
    return result;
  }

  async exportConfig() {
    return this._ws({ type: `${DOMAIN}/export_config` });
  }

  async agentSpec() {
    return this._ws({ type: `${DOMAIN}/get_agent_spec` });
  }
}

