from pathlib import Path
from datetime import datetime


from sqlalchemy import Integer, create_engine, String, Boolean, select, ForeignKey, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, DeclarativeBase, Mapped, mapped_column, relationship

from werkzeug.security import generate_password_hash, check_password_hash

from app_paths import garantir_arquivo_gravavel

pasta_atual = Path(__file__).parent
PATH_TO_DB = garantir_arquivo_gravavel("bd_usuarios.sqlite")
DATE_FORMAT = "%Y-%m-%d"
TIPO_FERIAS = "ferias"


def _cor_evento_por_tipo(tipo):
    cores = {
        "ferias": "#2f80ed",
        "folga": "#27ae60",
        "atestado": "#f2994a",
    }
    return cores.get(tipo, "#6c757d")


def _titulo_evento_por_tipo(tipo):
    titulos = {
        "ferias": "Férias",
        "folga": "Folga",
        "atestado": "Atestado",
    }
    return titulos.get(tipo, "Ocorrência")


class EmailJaCadastradoError(ValueError):
    pass

class Base(DeclarativeBase):
    pass


class UsuarioFerias(Base):
    __tablename__ = "usuarios_ferias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    senha: Mapped[str] = mapped_column(String(128), nullable=False)
    acesso_gestor: Mapped[bool] = mapped_column(Boolean(), default=False)
    inicio_na_empresa: Mapped[str] = mapped_column(String(30), nullable=False)
    recurso_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    eventos_ferias: Mapped[list["EventosFerias"]] = relationship(
        back_populates="parent",
        lazy="subquery",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"UsuarioFerias({self.id}, {self.nome})"

    def define_senha(self, senha):
        self.senha = generate_password_hash(senha)

    def verifica_senha(self, senha):
        return check_password_hash(self.senha, senha)
    
    def adiciona_ferias(self, inicio_ferias, fim_ferias, tipo=TIPO_FERIAS):
        total_dias = (
            datetime.strptime(fim_ferias, DATE_FORMAT)
            - datetime.strptime(inicio_ferias, DATE_FORMAT)
        ).days + 1
        with Session(bind=engine) as session:
            ferias = EventosFerias(
                parent_id=self.id,
                inicio_ferias=inicio_ferias,
                fim_ferias=fim_ferias,
                total_dias=total_dias,
                tipo=tipo,
            )
            session.add(ferias)
            session.commit()

    def adicona_ferias(self, inicio_ferias, fim_ferias, tipo=TIPO_FERIAS):
        self.adiciona_ferias(inicio_ferias, fim_ferias, tipo=tipo)

    def lista_ferias(self):
        lista_eventos = []
        for evento in self.eventos_ferias:
            cor_evento = _cor_evento_por_tipo(evento.tipo)
            lista_eventos.append({
                "id": str(evento.id),
                "title": f"{_titulo_evento_por_tipo(evento.tipo)}: {self.nome}",
                "start": evento.inicio_ferias,
                "end": evento.fim_ferias,
                "resourceId": self.recurso_id or "sem-equipe",
                "backgroundColor": cor_evento,
                "borderColor": cor_evento,
                "extendedProps": {
                    "usuario_id": self.id,
                    "usuario_nome": self.nome,
                    "total_dias": evento.total_dias,
                    "tipo": evento.tipo,
                    "recurso_id": self.recurso_id or "sem-equipe",
                },
            })
        return lista_eventos
    
    def dias_para_solicitar(self):

        total_dias = (
            datetime.now() - datetime.strptime(self.inicio_na_empresa, DATE_FORMAT)
        ).days * (30 / 365)
        dias_tirados = 0
        for evento in self.eventos_ferias:
            if evento.tipo == TIPO_FERIAS:
                dias_tirados += evento.total_dias
        return int(total_dias - dias_tirados)
    

class EventosFerias(Base):
    __tablename__ = "eventos_ferias"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("usuarios_ferias.id"), nullable=False)
    parent: Mapped["UsuarioFerias"] = relationship(back_populates="eventos_ferias", lazy="subquery")
    inicio_ferias: Mapped[str] = mapped_column(String(30), nullable=False)
    fim_ferias: Mapped[str] = mapped_column(String(30), nullable=False)
    total_dias: Mapped[int] = mapped_column(Integer(), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, default=TIPO_FERIAS)
    

engine = create_engine(f"sqlite:///{PATH_TO_DB}")
Base.metadata.create_all(bind=engine)


def _garantir_colunas_db():
    inspector = inspect(engine)
    colunas_usuario = {coluna["name"] for coluna in inspector.get_columns("usuarios_ferias")}
    colunas_evento = {coluna["name"] for coluna in inspector.get_columns("eventos_ferias")}

    with engine.begin() as conexao:
        if "recurso_id" not in colunas_usuario:
            conexao.exec_driver_sql("ALTER TABLE usuarios_ferias ADD COLUMN recurso_id VARCHAR(50)")
        if "tipo" not in colunas_evento:
            conexao.exec_driver_sql(
                "ALTER TABLE eventos_ferias ADD COLUMN tipo VARCHAR(30) NOT NULL DEFAULT 'ferias'"
            )


_garantir_colunas_db()

# CRUD - Create, Read, Update, Delete
def _normalizar_data(valor):
    if hasattr(valor, "strftime"):
        return valor.strftime(DATE_FORMAT)
    return valor


def _buscar_usuario(session, usuario_id):
    return session.scalar(select(UsuarioFerias).filter_by(id=usuario_id))


def _buscar_usuario_por_email(session, email):
    return session.scalar(select(UsuarioFerias).filter_by(email=email))


def _buscar_ferias(session, ferias_id):
    return session.scalar(select(EventosFerias).filter_by(id=ferias_id))


def criar_usuario(nome, senha, email, **kwargs):
    with Session(bind=engine) as session:
        if _buscar_usuario_por_email(session, email) is not None:
            raise EmailJaCadastradoError("Ja existe um usuario com este e-mail.")

        dados_usuario = {key: _normalizar_data(value) for key, value in kwargs.items()}
        usuario = UsuarioFerias(nome=nome, email=email, **dados_usuario)
        usuario.define_senha(senha)
        session.add(usuario)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise EmailJaCadastradoError("Ja existe um usuario com este e-mail.") from exc


def ler_todos_usuarios():
    with Session(bind=engine) as session:
        return list(session.scalars(select(UsuarioFerias)))
    

def ler_usuario_por_id(id):
    with Session(bind=engine) as session:
        return _buscar_usuario(session, id)


def modificar_usuario(id, **kwargs):
    with Session(bind=engine) as session:
        usuario = _buscar_usuario(session, id)
        if usuario is None:
            return

        novo_email = kwargs.get("email")
        if novo_email:
            usuario_com_mesmo_email = _buscar_usuario_por_email(session, novo_email)
            if usuario_com_mesmo_email is not None and usuario_com_mesmo_email.id != id:
                raise EmailJaCadastradoError("Ja existe um usuario com este e-mail.")

        for key, value in kwargs.items():
            valor_normalizado = _normalizar_data(value)
            if key == "senha":
                usuario.define_senha(valor_normalizado)
            else:
                setattr(usuario, key, valor_normalizado)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise EmailJaCadastradoError("Ja existe um usuario com este e-mail.") from exc


def deletar_usuario(id):
    with Session(bind=engine) as session:
        usuario = _buscar_usuario(session, id)
        if usuario is None:
            return

        session.delete(usuario)
        session.commit()


def atualizar_ferias(ferias_id, inicio_ferias, fim_ferias, tipo=TIPO_FERIAS):
    with Session(bind=engine) as session:
        ferias = _buscar_ferias(session, ferias_id)
        if ferias is None:
            return None

        inicio_normalizado = _normalizar_data(inicio_ferias)
        fim_normalizado = _normalizar_data(fim_ferias)
        total_dias = (
            datetime.strptime(fim_normalizado, DATE_FORMAT)
            - datetime.strptime(inicio_normalizado, DATE_FORMAT)
        ).days + 1

        ferias.inicio_ferias = inicio_normalizado
        ferias.fim_ferias = fim_normalizado
        ferias.total_dias = total_dias
        ferias.tipo = tipo
        session.commit()
        return ferias


def deletar_ferias(ferias_id):
    with Session(bind=engine) as session:
        ferias = _buscar_ferias(session, ferias_id)
        if ferias is None:
            return False

        session.delete(ferias)
        session.commit()
        return True

if __name__ == "__main__":
    pass
    
    # criar_usuario("Rony Franzini",
    #                senha="senha123", 
    #                email="rony.franzini@gmail.com", 
    #                acesso_gestor=True,
    #                inicio_na_empresa="2022-01-01")
    
    # criar_usuario("Andreia Franzini",
    #                senha="senha123", 
    #                email="andreia.franzini@gmail.com", 
    #                acesso_gestor=False,
    #                inicio_na_empresa="2022-01-01")
