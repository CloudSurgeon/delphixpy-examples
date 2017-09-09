#!/usr/bin/env python
#For use with HipChat and Will
#https://github.com/skoczen/will

from will.plugin import WillPlugin
from will.decorators import respond_to, periodic, hear, randomly, route, rendered_template, require_settings
from delphixpy.v1_6_0.delphix_engine import DelphixEngine
from delphixpy.v1_6_0.web import group, database
from delphixpy.v1_6_0 import job_context

class DelphixSnapshotPlugin(WillPlugin):
    
    @respond_to("snapshot_group (?P<v_object>.*)")
    def snapshot_group_will(self, message, v_object=None):
        group_name = v_object
        #database_name = "Employee DB - Dev"

        server_session = DelphixEngine("landsharkengine", "delphix_admin", "landshark", "DOMAIN")

        all_groups = group.get_all(server_session)

        for each in all_groups:
            if group_name == each.name:
                group_reference = each.reference
                break

        database_objs = database.get_all(server_session, group=group_reference)

        with job_context.async(server_session):
            for obj in database_objs:
                database.sync(server_session, obj.reference)
