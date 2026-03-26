'use strict';

const { validate, getReasonMessage } = require('./license/validator');

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

    try {
      const permissionActions = [
        // Project
        'api::project.project.find',
        'api::project.project.findOne',
        'api::project.project.create',
        'api::project.project.update',
        'api::project.project.delete',
        // Machine
        'api::machine.machine.find',
        'api::machine.machine.findOne',
        'api::machine.machine.create',
        'api::machine.machine.update',
        'api::machine.machine.delete',
        // Process (Custom)
        'api::process.process.launch',
        'api::process.process.stop',
      ];

      const bootstrapPermissions = async (roleType) => {
        const role = await strapi.db.query('plugin::users-permissions.role').findOne({
          where: { type: roleType },
        });

        if (role) {
          await Promise.all(permissionActions.map(async (action) => {
            const count = await strapi.db.query('plugin::users-permissions.permission').count({
              where: {
                role: role.id,
                action: action
              }
            });
            
            if (count === 0) {
              await strapi.db.query('plugin::users-permissions.permission').create({
                data: {
                  action: action,
                  role: role.id,
                  enabled: true
                }
              });
              strapi.log.info(`Granted ${roleType} permission: ${action}`);
            }
          }));
        }
        return role;
      };

      // 1. Bootstrap Permissions for Public and Authenticated
      await bootstrapPermissions('public');
      const authenticatedRole = await bootstrapPermissions('authenticated');

      // 2. Create Default User (admin / Password123!)
      if (authenticatedRole) {
        const userCount = await strapi.db.query('plugin::users-permissions.user').count({
          where: { email: 'admin@what-tech.cn' }
        });

        if (userCount === 0) {
          await strapi.entityService.create('plugin::users-permissions.user', {
            data: {
              username: 'admin',
              email: 'admin@what-tech.cn',
              password: 'Password123!',
              confirmed: true,
              blocked: false,
              role: authenticatedRole.id
            }
          });
          strapi.log.info('Created default user: admin@what-tech.cn / Password123!');
        }
      }

    } catch (e) {
      strapi.log.error('Failed to bootstrap permissions or user', e);
    }
  },
};
