const DOMAIN = "benni_core_devices";

export class Store {
  constructor() {
    this.hass = null;
    this.status = null;
    this.catalog = null;
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

  async bulkImport(payload) {
    const result = await this._ws({ type: `${DOMAIN}/bulk_import`, payload });
    await this.refresh();
    return result;
  }
}

