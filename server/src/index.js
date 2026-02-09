'use strict';

module.exports = {
  /**
   * An asynchronous register function that runs before
   * your application is initialized.
   *
   * This gives you an opportunity to extend code.
   */
  register(/*{ strapi }*/) {},

  /**
   * An asynchronous bootstrap function that runs before
   * your application gets started.
   *
   * This gives you an opportunity to set up your data model,
   * run jobs, or perform some special logic.
   */
  async bootstrap({ strapi }) {
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
