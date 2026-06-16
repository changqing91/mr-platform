'use strict';

const { validate, getReasonMessage } = require('./license/validator');

const SEED_ROLES = [
  { name: 'VP',           canManage: true,  isSystem: true },
  { name: '数字主管',      canManage: true,  isSystem: true },
  { name: '可视化专员',    canManage: true,  isSystem: true },
  { name: '造型设计师',    canManage: false, isSystem: true },
  { name: '数字模型师',    canManage: false, isSystem: true },
];

module.exports = {
  register(/*{ strapi }*/) {},

  async bootstrap({ strapi }) {
    // --- 许可证校验 ---
    const licenseResult = validate();
    if (licenseResult.valid) {
      strapi.log.info(`[License] 有效 · 客户: ${licenseResult.customer} · 到期: ${licenseResult.expires_at}`);
    } else {
      strapi.log.warn(`[License] 无效: ${getReasonMessage(licenseResult.reason)}`);
      strapi.log.warn(`[License] 当前机器 ID: ${licenseResult.current_machine_id}`);
      strapi.log.warn('[License] 系统将启动，但所有 API 请求将被拦截，直到上传有效许可证。');
    }

    // --- 自动放行 public 角色调用 license/process custom 路由 ---
    try {
      const publicActions = [
        'api::license.license.status',
        'api::license.license.upload',
        'api::process.process.executePython',
      ];
      const role = await strapi.db.query('plugin::users-permissions.role').findOne({
        where: { type: 'public' },
      });
      if (role) {
        await Promise.all(publicActions.map(async (action) => {
          const count = await strapi.db.query('plugin::users-permissions.permission').count({
            where: { role: role.id, action },
          });
          if (count === 0) {
            await strapi.db.query('plugin::users-permissions.permission').create({
              data: { action, role: role.id, enabled: true },
            });
          }
        }));
      }
    } catch (e) {
      strapi.log.warn('[bootstrap] failed to grant public permissions for license/process custom endpoints', e);
    }

    // --- Seed 内置 app-role ---
    try {
      for (const seed of SEED_ROLES) {
        const existing = await strapi.db.query('api::app-role.app-role').findOne({ where: { name: seed.name } });
        if (!existing) {
          await strapi.entityService.create('api::app-role.app-role', { data: seed });
          strapi.log.info(`[bootstrap] created seed app-role: ${seed.name}`);
        } else if (!existing.isSystem) {
          await strapi.entityService.update('api::app-role.app-role', existing.id, { data: { isSystem: true } });
        }
      }
    } catch (e) {
      strapi.log.error('[bootstrap] failed to seed app-roles', e);
    }
  },
};
