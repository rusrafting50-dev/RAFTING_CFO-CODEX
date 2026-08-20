"""Регистрация всех blueprint'ов приложения."""


def register_blueprints(app):
    from routes.main import bp as main_bp
    from routes.competitions import bp as competitions_bp
    from routes.team import bp as team_bp
    from routes.referees import bp as referees_bp
    from routes.events import bp as events_bp
    from routes.federation import bp as federation_bp
    from routes.regions import bp as regions_bp
    from routes.clubs import bp as clubs_bp
    from routes.admin import bp as admin_bp
    from routes.api import bp as api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(competitions_bp, url_prefix='/competitions')
    app.register_blueprint(team_bp, url_prefix='/team')
    app.register_blueprint(referees_bp, url_prefix='/referees')
    app.register_blueprint(events_bp, url_prefix='/events')
    app.register_blueprint(federation_bp, url_prefix='/federation')
    app.register_blueprint(regions_bp, url_prefix='/regions')
    app.register_blueprint(clubs_bp, url_prefix='/clubs')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
